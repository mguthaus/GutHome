import sqlite3
import threading
from flask import Flask, render_template_string
import config
from collector import init_db, run_collector
from govee_collector import init_govee_db, run_govee_collector
from weather_collector import init_weather_db, run_weather_collector

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Sensibo Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #1a1a2e;
            color: #e0e0e0;
        }
        h1 {
            text-align: center;
            color: #e0e0e0;
            margin-bottom: 5px;
        }
        .subtitle {
            text-align: center;
            color: #888;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .chart {
            background: #16213e;
            border-radius: 12px;
            padding: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .current-values {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 25px;
            flex-wrap: wrap;
        }
        .device-card {
            background: #16213e;
            border-radius: 12px;
            padding: 15px 25px;
            min-width: 200px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .device-card h3 {
            margin: 0 0 10px 0;
            font-size: 16px;
        }
        .device-card .metric {
            display: flex;
            justify-content: space-between;
            padding: 3px 0;
            font-size: 14px;
        }
        .device-card .value {
            font-weight: bold;
        }
        .controls {
            text-align: center;
            margin-bottom: 20px;
        }
        .controls button {
            background: #0f3460;
            color: #e0e0e0;
            border: 1px solid #1a5276;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            margin: 0 5px;
            font-size: 14px;
        }
        .controls button:hover {
            background: #1a5276;
        }
        .controls button.active {
            background: #e94560;
            border-color: #e94560;
        }
        .chart-section {
            margin-bottom: 25px;
        }
        .checkboxes {
            text-align: center;
            margin-bottom: 8px;
        }
        .checkboxes label {
            margin: 0 12px;
            cursor: pointer;
            font-size: 14px;
        }
        .checkboxes input[type="checkbox"] {
            accent-color: #e94560;
            margin-right: 4px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <h1>Sensor Dashboard</h1>
    <div class="subtitle" id="lastUpdate"></div>

    <div class="current-values" id="currentValues"></div>

    <div class="controls">
        <button onclick="setRange('1h')">1 Hour</button>
        <button onclick="setRange('6h')">6 Hours</button>
        <button onclick="setRange('24h')" class="active">24 Hours</button>
        <button onclick="setRange('7d')">7 Days</button>
        <button onclick="setRange('all')">All</button>
    </div>

    <div class="chart-section">
        <div class="checkboxes" id="chart1Checks">
            <label><input type="checkbox" checked onchange="fetchAndPlot()" data-field="temperature"> Temperature</label>
            <label><input type="checkbox" checked onchange="fetchAndPlot()" data-field="humidity"> Humidity</label>
        </div>
        <div class="chart" id="chart1" style="height:450px"></div>
    </div>

    <div class="chart-section">
        <div class="checkboxes" id="chart2Checks">
            <label><input type="checkbox" checked onchange="fetchAndPlot()" data-field="co2"> CO₂</label>
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="tvoc"> TVOC</label>
            <label><input type="checkbox" checked onchange="fetchAndPlot()" data-field="iaq"> AQI/IAQ</label>
        </div>
        <div class="chart" id="chart2" style="height:450px"></div>
    </div>

    <script>
        const ROOM_COLORS = {
            'Living Room': '#e94560',
            'Den': '#0f9b58',
            'Bedroom': '#4285f4',
            'Living Room (Govee)': '#ff6b81',
            'Bedroom (Govee)': '#a29bfe',
            'Den (Govee)': '#55efc4',
            'Outside': '#ffd93d'
        };
        let currentRange = '24h';

        function setRange(range) {
            currentRange = range;
            document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            fetchAndPlot();
        }

        const FIELD_CONFIG = {
            temperature: { label: 'Temp', unit: '°F', color: '#e94560' },
            humidity:    { label: 'Humidity', unit: '%', color: '#f5a623' },
            co2:         { label: 'CO₂', unit: 'ppm', color: '#e94560' },
            tvoc:        { label: 'TVOC', unit: 'ppb', color: '#0f9b58' },
            iaq:         { label: 'AQI/IAQ', unit: '', color: '#4285f4' }
        };

        const ROOM_STYLES = {
            'Living Room': 'solid',
            'Den': 'dash',
            'Bedroom': 'dot',
            'Living Room (Govee)': 'solid',
            'Bedroom (Govee)': 'dashdot',
            'Den (Govee)': 'dash',
            'Outside': 'longdash'
        };

        function getCheckedFields(containerId) {
            let checks = document.querySelectorAll('#' + containerId + ' input[type=checkbox]');
            let fields = [];
            checks.forEach(cb => { if (cb.checked) fields.push(cb.dataset.field); });
            return fields;
        }

        function fetchAndPlot() {
            fetch('/api/data?range=' + currentRange)
                .then(r => r.json())
                .then(data => {
                    plotGeneric('chart1', data, getCheckedFields('chart1Checks'));
                    plotGeneric('chart2', data, getCheckedFields('chart2Checks'));
                    updateCurrentValues(data);
                });
        }

        const BASE_LAYOUT = {
            paper_bgcolor: '#16213e',
            plot_bgcolor: '#16213e',
            font: { color: '#e0e0e0' },
            margin: { t: 40, r: 80, b: 40, l: 80 },
            xaxis: { gridcolor: '#2a2a4a', type: 'date' },
            legend: {
                orientation: 'h',
                y: 1.15,
                x: 0.5,
                xanchor: 'center',
                bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#e0e0e0' }
            },
            hovermode: 'x unified'
        };

        function plotGeneric(divId, data, fields) {
            if (fields.length === 0) {
                Plotly.newPlot(divId, [], BASE_LAYOUT, { responsive: true });
                return;
            }
            let traces = [];
            let rooms = Object.keys(data);
            let useSecondAxis = fields.length > 1;

            for (let room of rooms) {
                let readings = data[room];
                let roomDash = ROOM_STYLES[room] || 'solid';
                fields.forEach((field, i) => {
                    let cfg = FIELD_CONFIG[field];
                    traces.push({
                        x: readings.map(r => r.timestamp),
                        y: readings.map(r => r[field]),
                        name: room + ' ' + cfg.label,
                        type: 'scatter',
                        mode: 'lines',
                        line: { color: cfg.color, width: 2, dash: roomDash },
                        yaxis: (useSecondAxis && i > 0) ? 'y2' : 'y'
                    });
                });
            }

            let firstCfg = FIELD_CONFIG[fields[0]];
            let yTitle = firstCfg.label + (firstCfg.unit ? ' (' + firstCfg.unit + ')' : '');
            let layout = Object.assign({}, BASE_LAYOUT, {
                yaxis: { title: yTitle, gridcolor: '#2a2a4a', side: 'left' }
            });

            if (useSecondAxis) {
                let otherLabels = fields.slice(1).map(f => {
                    let c = FIELD_CONFIG[f];
                    return c.label + (c.unit ? ' (' + c.unit + ')' : '');
                });
                layout.yaxis2 = {
                    title: otherLabels.join(' / '),
                    gridcolor: '#2a2a4a',
                    side: 'right',
                    overlaying: 'y'
                };
            }

            Plotly.newPlot(divId, traces, layout, { responsive: true });
        }

        function updateCurrentValues(data) {
            let html = '';
            let latestTime = '';
            for (let room of Object.keys(data)) {
                let readings = data[room];
                if (readings.length === 0) continue;
                let latest = readings[readings.length - 1];
                latestTime = new Date(latest.timestamp).toLocaleString();
                let color = ROOM_COLORS[room] || '#fff';
                let metrics = `
                        <div class="metric"><span>Temp</span><span class="value">${latest.temperature?.toFixed(1) ?? '—'}°F</span></div>
                        <div class="metric"><span>Humidity</span><span class="value">${latest.humidity?.toFixed(0) ?? '—'}%</span></div>`;
                if (latest.co2 != null) metrics += `<div class="metric"><span>CO₂</span><span class="value">${latest.co2} ppm</span></div>`;
                if (latest.tvoc != null) metrics += `<div class="metric"><span>TVOC</span><span class="value">${latest.tvoc} ppb</span></div>`;
                if (latest.iaq != null) metrics += `<div class="metric"><span>AQI/IAQ</span><span class="value">${latest.iaq}</span></div>`;
                html += `
                    <div class="device-card" style="border-top: 3px solid ${color}">
                        <h3>${room}</h3>
                        ${metrics}
                    </div>
                `;
            }
            document.getElementById('currentValues').innerHTML = html;
            document.getElementById('lastUpdate').textContent = 'Last reading: ' + latestTime;
        }

        fetchAndPlot();
        setInterval(fetchAndPlot, 60000);
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/data")
def api_data():
    from flask import request
    import datetime

    range_param = request.args.get("range", "24h")
    now = datetime.datetime.utcnow()

    range_map = {
        "1h": datetime.timedelta(hours=1),
        "6h": datetime.timedelta(hours=6),
        "24h": datetime.timedelta(hours=24),
        "7d": datetime.timedelta(days=7),
    }

    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    if range_param in range_map:
        since = (now - range_map[range_param]).isoformat() + "Z"
        rows = conn.execute(
            "SELECT * FROM readings WHERE timestamp >= ? ORDER BY timestamp",
            (since,),
        ).fetchall()
        govee_rows = conn.execute(
            "SELECT * FROM govee_readings WHERE timestamp >= ? ORDER BY timestamp",
            (since,),
        ).fetchall()
        weather_rows = conn.execute(
            "SELECT * FROM weather_readings WHERE timestamp >= ? ORDER BY timestamp",
            (since,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM readings ORDER BY timestamp"
        ).fetchall()
        govee_rows = conn.execute(
            "SELECT * FROM govee_readings ORDER BY timestamp"
        ).fetchall()
        weather_rows = conn.execute(
            "SELECT * FROM weather_readings ORDER BY timestamp"
        ).fetchall()

    conn.close()

    result = {}
    for row in rows:
        room = row["room_name"]
        if room not in result:
            result[room] = []
        temp_c = row["temperature"]
        temp_f = round(temp_c * 9 / 5 + 32, 1) if temp_c is not None else None
        result[room].append(
            {
                "timestamp": row["timestamp"],
                "temperature": temp_f,
                "humidity": row["humidity"],
                "co2": row["co2"],
                "tvoc": row["tvoc"],
                "iaq": row["iaq"],
            }
        )

    for row in govee_rows:
        room = row["room_name"]
        if room not in result:
            result[room] = []
        temp_c = row["temperature"]
        temp_f = round(temp_c * 9 / 5 + 32, 1) if temp_c is not None else None
        result[room].append(
            {
                "timestamp": row["timestamp"],
                "temperature": temp_f,
                "humidity": row["humidity"],
                "co2": None,
                "tvoc": None,
                "iaq": None,
            }
        )

    for row in weather_rows:
        if "Outside" not in result:
            result["Outside"] = []
        result["Outside"].append(
            {
                "timestamp": row["timestamp"],
                "temperature": row["temperature"],
                "humidity": row["humidity"],
                "co2": None,
                "tvoc": None,
                "iaq": row["aqi"],
            }
        )

    return result


def main():
    init_db()
    init_govee_db()
    init_weather_db()
    collector_thread = threading.Thread(target=run_collector, daemon=True)
    collector_thread.start()
    govee_thread = threading.Thread(target=run_govee_collector, daemon=True)
    govee_thread.start()
    weather_thread = threading.Thread(target=run_weather_collector, daemon=True)
    weather_thread.start()
    print(f"\nDashboard running at http://localhost:{config.WEB_PORT}")
    app.run(host=config.WEB_HOST, port=config.WEB_PORT)


if __name__ == "__main__":
    main()
