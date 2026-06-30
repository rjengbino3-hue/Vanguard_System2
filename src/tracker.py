import math
import time


class VanguardTracker:
    def __init__(
        self,
        line_y=0.60,
        cooldown_seconds=300,
        iou_threshold=0.10,
        center_distance_threshold=0.28,
        size_similarity_threshold=0.25,
        object_memory_seconds=20,
        recent_event_suppression_seconds=0.0,
        recent_event_distance_threshold=0.25,
        recent_event_size_similarity=0.25,
    ):
        self.line_y = line_y
        self.cooldown_seconds = cooldown_seconds
        self.iou_threshold = iou_threshold
        self.center_distance_threshold = center_distance_threshold
        self.size_similarity_threshold = size_similarity_threshold
        self.object_memory_seconds = object_memory_seconds
        self.recent_event_suppression_seconds = recent_event_suppression_seconds
        self.recent_event_distance_threshold = recent_event_distance_threshold
        self.recent_event_size_similarity = recent_event_size_similarity

        self.next_object_id = 1
        self.objects = {}
        self.raw_track_aliases = {}
        self.previous_centers = {}
        self.logged_objects = {}

    def get_bbox_center(self, bbox):
        x_min, y_min, x_max, y_max = bbox
        return (x_min + x_max) / 2, (y_min + y_max) / 2

    def get_bbox_size(self, bbox):
        x_min, y_min, x_max, y_max = bbox
        return max(1e-6, x_max - x_min), max(1e-6, y_max - y_min)

    def get_iou(self, box_a, box_b):
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        intersection = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
        area_a = max(1e-6, (ax2 - ax1) * (ay2 - ay1))
        area_b = max(1e-6, (bx2 - bx1) * (by2 - by1))
        union = area_a + area_b - intersection

        return intersection / max(1e-6, union)

    def get_center_distance(self, box_a, box_b):
        ax, ay = self.get_bbox_center(box_a)
        bx, by = self.get_bbox_center(box_b)

        distance_squared = (ax - bx) ** 2 + (ay - by) ** 2

        if distance_squared < 0 or not math.isfinite(distance_squared):
            return float("inf")

        return math.sqrt(distance_squared)

    def get_size_similarity(self, box_a, box_b):
        aw, ah = self.get_bbox_size(box_a)
        bw, bh = self.get_bbox_size(box_b)

        width_similarity = min(aw, bw) / max(aw, bw)
        height_similarity = min(ah, bh) / max(ah, bh)

        return min(width_similarity, height_similarity)

    def cleanup_expired_objects(self, now):
        expired_ids = [
            object_id
            for object_id, data in self.objects.items()
            if now - data["last_seen"] > self.object_memory_seconds
        ]

        for object_id in expired_ids:
            raw_ids = self.objects[object_id].get("raw_track_ids", set())

            for raw_id in raw_ids:
                self.raw_track_aliases.pop(raw_id, None)

            self.objects.pop(object_id, None)
            self.previous_centers.pop(object_id, None)

    def create_object(self, raw_track_id, bbox, now):
        object_id = f"motorcycle-{self.next_object_id}"
        self.next_object_id += 1

        raw_ids = set()
        if raw_track_id is not None:
            raw_ids.add(raw_track_id)
            self.raw_track_aliases[raw_track_id] = object_id

        self.objects[object_id] = {
            "bbox": bbox,
            "last_seen": now,
            "raw_track_ids": raw_ids,
        }

        return object_id

    def update_object(self, object_id, raw_track_id, bbox, now):
        if object_id not in self.objects:
            return self.create_object(raw_track_id, bbox, now)

        self.objects[object_id]["bbox"] = bbox
        self.objects[object_id]["last_seen"] = now

        if raw_track_id is not None:
            self.objects[object_id]["raw_track_ids"].add(raw_track_id)
            self.raw_track_aliases[raw_track_id] = object_id

        return object_id

    def find_matching_object(self, bbox, now):
        best_object_id = None
        best_score = -1.0

        for object_id, data in self.objects.items():
            if now - data["last_seen"] > self.object_memory_seconds:
                continue

            previous_bbox = data["bbox"]

            iou = self.get_iou(bbox, previous_bbox)
            center_distance = self.get_center_distance(bbox, previous_bbox)
            size_similarity = self.get_size_similarity(bbox, previous_bbox)

            center_match = center_distance <= self.center_distance_threshold
            iou_match = iou >= self.iou_threshold
            size_match = size_similarity >= self.size_similarity_threshold

            if not size_match:
                continue

            if not (iou_match or center_match):
                continue

            score = iou + (1.0 - min(center_distance, 1.0)) + size_similarity

            if score > best_score:
                best_score = score
                best_object_id = object_id

        return best_object_id

    def get_stable_object_id(self, raw_track_id, bbox):
        now = time.time()
        self.cleanup_expired_objects(now)

        if raw_track_id is not None and raw_track_id in self.raw_track_aliases:
            object_id = self.raw_track_aliases[raw_track_id]
            return self.update_object(object_id, raw_track_id, bbox, now)

        matched_object_id = self.find_matching_object(bbox, now)

        if matched_object_id is not None:
            return self.update_object(matched_object_id, raw_track_id, bbox, now)

        return self.create_object(raw_track_id, bbox, now)

    def crossed_line(self, object_id, bbox):
        _, current_y = self.get_bbox_center(bbox)

        previous_y = self.previous_centers.get(object_id)
        self.previous_centers[object_id] = current_y

        if previous_y is None:
            return False

        return previous_y < self.line_y <= current_y

    def should_count_object(self, object_id):
        return object_id not in self.logged_objects

    def mark_object_counted(self, object_id):
        self.logged_objects[object_id] = time.time()

    def remember_logged_event(self, object_id, bbox):
        self.mark_object_counted(object_id)
