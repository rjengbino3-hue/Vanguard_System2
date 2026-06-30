import json
import os
import threading
import time

import hailo

from src.database import (
    save_violation,
    fetch_device_cloud_config,
    update_device_telemetry,
)
from src.tracker import VanguardTracker


class VanguardPipeline:
    def __init__(self):
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.settings = self.load_json("config/settings.json")
        self.device_id = self.settings["device"]["device_id"]

        self.upload_lock = threading.Lock()
        self.in_flight_uploads = set()

        print(f"\n[SYSTEM] Booting Edge Node ID: {self.device_id}")
        print("[SYSTEM] Fetching active site deployment assignment from Supabase...")

        cloud_location_name = fetch_device_cloud_config(self.device_id)
        self.selected_location = None

        if cloud_location_name:
            for location in self.settings["locations"]:
                if location["name"] == cloud_location_name:
                    self.selected_location = location
                    print(f"[SYSTEM] Cloud Sync Success! Deployment Target Locked: {cloud_location_name}")
                    break

        if not self.selected_location:
            print("[SYSTEM] Warning: Cloud location unavailable. Using default JSON backup profile.")
            self.selected_location = self.settings["locations"][0]

        update_device_telemetry(
            self.device_id,
            status="online",
            fps=int(self.settings["video"]["fps"]),
        )

        model_settings = self.settings["model"]
        analytics_settings = self.settings["analytics"]

        self.confidence_threshold = model_settings["confidence_threshold"]
        self.motorcycle_label = analytics_settings["motorcycle_label"]
        self.excluded_vehicle_labels = set(analytics_settings["excluded_vehicle_labels"])
        self.violation_rider_labels = set(analytics_settings["violation_rider_labels"])
        self.compliant_rider_labels = set(analytics_settings["compliant_rider_labels"])

        self.line_crossing_enabled = analytics_settings.get("line_crossing_enabled", False)
        self.debug_decisions = analytics_settings.get("debug_decisions", True)
        self.min_overlap_ratio = analytics_settings.get("min_overlap_ratio", 0.04)
        self.near_distance_threshold = analytics_settings.get("near_distance_threshold", 0.22)

        self.required_violation_votes = analytics_settings.get("required_violation_votes", 2)
        self.violation_vote_window = analytics_settings.get("violation_vote_window", 4)
        self.violation_confirmation_timeout = analytics_settings.get("violation_confirmation_timeout", 1.5)
        self.violation_candidates = {}

        self.tracker = VanguardTracker(
            line_y=analytics_settings.get("virtual_line_y", 0.60),
            cooldown_seconds=analytics_settings.get("duplicate_cooldown_seconds", 300),
            iou_threshold=analytics_settings.get("fallback_iou_threshold", 0.10),
            center_distance_threshold=analytics_settings.get("fallback_center_distance_threshold", 0.28),
            size_similarity_threshold=analytics_settings.get("fallback_size_similarity", 0.25),
            object_memory_seconds=analytics_settings.get("object_memory_seconds", 20),
            recent_event_suppression_seconds=analytics_settings.get("recent_event_suppression_seconds", 0.0),
            recent_event_distance_threshold=analytics_settings.get("recent_event_distance_threshold", 0.25),
            recent_event_size_similarity=analytics_settings.get("recent_event_size_similarity", 0.25),
        )

        self.db_name = self.settings["database"]["db_name"]

        print(
            "[SYSTEM] Runtime analytics settings | "
            f"line_crossing_enabled={self.line_crossing_enabled} | "
            f"confidence_threshold={self.confidence_threshold} | "
            f"near_distance_threshold={self.near_distance_threshold} | "
            f"votes={self.required_violation_votes}/{self.violation_vote_window}"
        )

    def load_json(self, relative_path):
        file_path = os.path.join(self.project_root, relative_path)

        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def debug_log(self, message):
        if self.debug_decisions:
            print(message)

    def process_hailo_buffer(self, buffer):
        roi = hailo.get_roi_from_buffer(buffer)
        detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

        vehicles = []
        rider_statuses = []

        for detection in detections:
            label = detection.get_label()
            confidence = detection.get_confidence()

            if confidence < self.confidence_threshold:
                continue

            detection_data = {
                "label": label,
                "confidence": confidence,
                "bbox": self.get_bbox(detection),
                "track_id": self.get_track_id(detection),
            }

            if label == self.motorcycle_label or label in self.excluded_vehicle_labels:
                vehicles.append(detection_data)
            elif label in self.violation_rider_labels or label in self.compliant_rider_labels:
                rider_statuses.append(detection_data)

        if vehicles or rider_statuses:
            self.debug_log(
                "[FRAME] "
                f"vehicles={[vehicle['label'] for vehicle in vehicles]} | "
                f"rider_statuses={[rider['label'] for rider in rider_statuses]}"
            )

        for vehicle in vehicles:
            self.evaluate_vehicle(vehicle, rider_statuses)

    def evaluate_vehicle(self, vehicle, rider_statuses):
        vehicle_label = vehicle["label"]
        raw_track_id = vehicle["track_id"]
        vehicle_bbox = vehicle["bbox"]

        if vehicle_label in self.excluded_vehicle_labels:
            self.debug_log(f"[DECISION] {vehicle_label} ignored by exclusion rule.")
            return

        if vehicle_label != self.motorcycle_label:
            self.debug_log(f"[DECISION] {vehicle_label} ignored because it is not motorcycle.")
            return

        stable_object_id = self.tracker.get_stable_object_id(raw_track_id, vehicle_bbox)

        overlapping_riders = [
            rider
            for rider in rider_statuses
            if self.boxes_overlap_or_near(rider["bbox"], vehicle_bbox)
        ]

        overlapping_labels = [rider["label"] for rider in overlapping_riders]

        has_violation_rider = any(
            rider["label"] in self.violation_rider_labels
            for rider in overlapping_riders
        )

        has_compliant_rider = any(
            rider["label"] in self.compliant_rider_labels
            for rider in overlapping_riders
        )

        violation_votes = self.record_violation_vote(stable_object_id, has_violation_rider)

        self.debug_log(
            f"[DECISION] Motorcycle {stable_object_id} detected | "
            f"raw_track_id={raw_track_id} | "
            f"overlapping_riders={overlapping_labels} | "
            f"violation_votes={violation_votes}/{self.required_violation_votes}"
        )

        if not has_violation_rider:
            if has_compliant_rider:
                self.debug_log(f"[DECISION] Motorcycle {stable_object_id} compliant/currently no violation.")
            else:
                self.debug_log(f"[DECISION] Motorcycle {stable_object_id} no violation rider overlap.")
            return

        if violation_votes < self.required_violation_votes:
            self.debug_log(
                f"[DECISION] Motorcycle {stable_object_id} waiting for violation vote confirmation."
            )
            return

        if self.line_crossing_enabled and not self.tracker.crossed_line(stable_object_id, vehicle_bbox):
            self.debug_log(f"[DECISION] Motorcycle {stable_object_id} violation found, but line not crossed.")
            return

        if not self.tracker.should_count_object(stable_object_id):
            self.debug_log(f"[DECISION] Motorcycle {stable_object_id} already counted in this runtime.")
            return

        with self.upload_lock:
            if stable_object_id in self.in_flight_uploads:
                self.debug_log(f"[DECISION] Motorcycle {stable_object_id} upload already in flight.")
                return

            self.in_flight_uploads.add(stable_object_id)

        self.tracker.remember_logged_event(stable_object_id, vehicle_bbox)
        self.violation_candidates.pop(stable_object_id, None)

        violation_confidence = self.get_highest_violation_confidence(overlapping_riders)

        db_worker = threading.Thread(
            target=self._async_save_violation,
            args=(violation_confidence, stable_object_id),
        )
        db_worker.daemon = True
        db_worker.start()

        print(
            "[VANGUARD] 1 violation logged for motorcycle | "
            f"stable_id={stable_object_id} | "
            f"raw_track_id={raw_track_id} | "
            f"riders={overlapping_labels} | "
            f"confidence={violation_confidence:.2f}"
        )

    def record_violation_vote(self, stable_object_id, has_violation_rider):
        now = time.time()
        candidate = self.violation_candidates.get(stable_object_id)

        if candidate is None or now - candidate["last_seen"] > self.violation_confirmation_timeout:
            candidate = {
                "votes": [],
                "last_seen": now,
            }

        candidate["votes"].append(bool(has_violation_rider))
        candidate["votes"] = candidate["votes"][-self.violation_vote_window:]
        candidate["last_seen"] = now

        self.violation_candidates[stable_object_id] = candidate

        return sum(candidate["votes"])

    def _async_save_violation(self, violation_confidence, stable_object_id):
        try:
            save_violation(
                device_id=self.device_id,
                violation_type="helmet_violation_per_motorcycle",
                class_name="motorcycle_with_no_or_invalid_helmet",
                confidence=violation_confidence,
                location=self.selected_location["name"],
                latitude=self.selected_location["latitude"],
                longitude=self.selected_location["longitude"],
                tracking_id=stable_object_id,
                db_name=self.db_name,
            )

            print(f"[BACKGROUND THREAD] Supabase logged successfully | stable_id={stable_object_id}")

        except Exception as error:
            print(f"[BACKGROUND THREAD ERROR] Failed sending log to Supabase: {error}")

        finally:
            with self.upload_lock:
                self.in_flight_uploads.discard(stable_object_id)

    def get_bbox(self, detection):
        bbox = detection.get_bbox()

        x_min = bbox.xmin()
        y_min = bbox.ymin()
        x_max = x_min + bbox.width()
        y_max = y_min + bbox.height()

        return [x_min, y_min, x_max, y_max]

    def get_track_id(self, detection):
        try:
            track_objects = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)

            if len(track_objects) == 1:
                return track_objects[0].get_id()

        except Exception:
            return None

        return None

    def boxes_overlap_or_near(self, rider_box, vehicle_box):
        rx1, ry1, rx2, ry2 = rider_box
        vx1, vy1, vx2, vy2 = vehicle_box

        overlap_x1 = max(rx1, vx1)
        overlap_y1 = max(ry1, vy1)
        overlap_x2 = min(rx2, vx2)
        overlap_y2 = min(ry2, vy2)

        overlap_width = max(0, overlap_x2 - overlap_x1)
        overlap_height = max(0, overlap_y2 - overlap_y1)
        overlap_area = overlap_width * overlap_height

        rider_area = max(1e-6, (rx2 - rx1) * (ry2 - ry1))
        overlap_ratio = overlap_area / rider_area

        if overlap_ratio >= self.min_overlap_ratio:
            return True

        rider_center_x = (rx1 + rx2) / 2
        rider_center_y = (ry1 + ry2) / 2
        vehicle_center_x = (vx1 + vx2) / 2
        vehicle_center_y = (vy1 + vy2) / 2

        horizontal_distance = abs(rider_center_x - vehicle_center_x)
        vertical_distance = abs(rider_center_y - vehicle_center_y)

        return (
            horizontal_distance <= self.near_distance_threshold
            and vertical_distance <= self.near_distance_threshold
        )

    def get_highest_violation_confidence(self, riders):
        violation_confidences = [
            rider["confidence"]
            for rider in riders
            if rider["label"] in self.violation_rider_labels
        ]

        return max(violation_confidences) if violation_confidences else 0.0
