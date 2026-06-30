/* ==========================================================================
   VANGUARD ANALYTICS PORTAL - SAFE SECURE GLOBAL CHARTS ENGINE
   ========================================================================== */

// 1. REUSABLE CONFIGURATION FACTORY FOR POPPINS TYPOGRAPHY & DYNAMIC HOVER TOOLTIPS
const getGlobalChartOptions = (maxYValue = 250, stepSizeValue = 50) => {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { 
                display: false 
            },
            tooltip: {
                enabled: true,
                backgroundColor: 'rgba(15, 23, 42, 0.95)', // Sleek slate-900 background tint
                titleFont: { family: 'Poppins', size: 11, weight: '700' },
                bodyFont: { family: 'Poppins', size: 12, weight: '900' },
                padding: 10,
                cornerRadius: 8,
                displayColors: false,
                callbacks: {
                    label: function(context) { 
                        return context.parsed.y + ' violations'; 
                    }
                }
            }
        },
        scales: {
            y: {
                min: 0, 
                max: maxYValue,
                ticks: { 
                    stepSize: stepSizeValue, 
                    color: '#94a3b8', 
                    font: { family: 'Poppins', size: 10 } 
                },
                grid: { color: '#f1f5f9' }, 
                border: { display: false }
            },
            x: {
                ticks: {
                    color: '#000000',
                    font: { family: 'Poppins', weight: '700', size: 9 },
                    callback: function(val) {
                        const targets = ['12 AM', '3 AM', '6 AM', '9 AM', '12 PM', '3 PM', '6 PM', '9 PM'];
                        const labelString = this.getLabelForValue(val);
                        return targets.includes(labelString) ? labelString : '';
                    }
                },
                grid: { display: false }
            }
        }
    };
};

// 2. SHARED INTERACTIVE METRIC DATASETS
const hourlyLabels = [
    '12 AM', '1 AM', '2 AM', '3 AM', '4 AM', '5 AM', '6 AM', '7 AM', '8 AM', '9 AM', '10 AM', '11 AM', 
    '12 PM', '1 PM', '2 PM', '3 PM', '4 PM', '5 PM', '6 PM', '7 PM', '8 PM', '9 PM', '10 PM', '11 PM'
];
const hourlyData = [25, 35, 70, 95, 80, 110, 90, 165, 212, 170, 110, 92, 105, 98, 64, 80, 55, 45, 25, 70, 98, 80, 110, 65];

// 3. SECURE DOM LOADING HOOKS TO PREVENT SCRIPT CRASHES
document.addEventListener('DOMContentLoaded', () => {
    console.log("Charts engine initialized safely...");

    // --- CHART A: OVERVIEW BAR CHART ---
    const overviewEl = document.getElementById('overviewBarChart');
    if (overviewEl) {
        console.log("Rendering overviewBarChart...");
        new Chart(overviewEl.getContext('2d'), {
            type: 'bar',
            data: {
                labels: hourlyLabels,
                datasets: [{
                    data: hourlyData,
                    backgroundColor: '#0284c7',
                    hoverBackgroundColor: '#1d4ed8',
                    borderRadius: 4,
                    barPercentage: 0.6
                }]
            },
            options: getGlobalChartOptions(250, 50)
        });
    }

    // --- CHART B: HISTORY REPORT PAGE MINI BAR CHART ---
    const historyEl = document.getElementById('historyHourlyChart');
    if (historyEl) {
        console.log("Rendering historyHourlyChart...");
        new Chart(historyEl.getContext('2d'), {
            type: 'bar',
            data: {
                labels: hourlyLabels,
                datasets: [{
                    data: hourlyData,
                    backgroundColor: '#0284c7',
                    hoverBackgroundColor: '#1d4ed8',
                    borderRadius: 4,
                    barPercentage: 0.6
                }]
            },
            options: getGlobalChartOptions(250, 50)
        });
    }

    // --- CHART C: TRENDS & METRICS WIDESCREEN BAR CHART ---
    const trendBarEl = document.getElementById('timeOfDayChartWidescreen');
    if (trendBarEl) {
        console.log("Rendering timeOfDayChartWidescreen...");
        new Chart(trendBarEl.getContext('2d'), {
            type: 'bar',
            data: {
                labels: hourlyLabels,
                datasets: [{
                    data: hourlyData,
                    backgroundColor: '#0284c7',
                    hoverBackgroundColor: '#1d4ed8',
                    borderRadius: 4,
                    barPercentage: 0.6
                }]
            },
            options: getGlobalChartOptions(250, 50)
        });
    }

    // --- CHART D: WEEKLY LINE CHART (USED IN OVERVIEW & TREND PAGES) ---
    const trendLineEl = document.getElementById('dayOfWeekChartWidescreen');
    if (trendLineEl) {
        console.log("Rendering dayOfWeekChartWidescreen...");
        new Chart(trendLineEl.getContext('2d'), {
            type: 'line',
            data: {
                labels: ['May 14', 'May 15', 'May 16', 'May 17', 'May 18', 'May 19'],
                datasets: [{
                    data: [182, 196, 221, 256, 196, 221],
                    borderColor: '#1d4ed8',
                    borderWidth: 2.5,
                    pointBackgroundColor: '#0284c7',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    tension: 0.2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        enabled: true,
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleFont: { family: 'Poppins', size: 11, weight: '700' },
                        bodyFont: { family: 'Poppins', size: 12, weight: '900' },
                        padding: 10,
                        cornerRadius: 8
                    }
                },
                scales: {
                    y: {
                        min: 0, max: 400,
                        ticks: { stepSize: 100, color: '#94a3b8', font: { family: 'Poppins', size: 10 } },
                        grid: { color: '#f1f5f9' }, border: { display: false }
                    },
                    x: { ticks: { color: '#64748b', font: { family: 'Poppins', size: 10 } }, grid: { display: false } }
                }
            }
        });
    }
});