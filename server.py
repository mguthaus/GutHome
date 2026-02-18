import sqlite3
import threading
from flask import Flask, render_template_string
import config
from collector import init_db, run_collector
from govee_collector import init_govee_db, run_govee_collector
from weather_collector import init_weather_db, run_weather_collector
from solar_collector import init_solar_db, run_solar_collector

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
        .controls input[type="date"],
        .controls select {
            background: #0f3460;
            color: #e0e0e0;
            border: 1px solid #1a5276;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
        }
        .source-label {
            font-size: 11px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 8px;
            padding-bottom: 2px;
            border-bottom: 1px solid #2a2a4a;
        }
        .source-label:first-child {
            margin-top: 0;
        }
        .cb-group {
            margin: 0 10px;
            color: #888;
            font-size: 13px;
        }
        .cb-group label {
            color: #e0e0e0;
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
        <button onclick="setRange('30d')">30 Days</button>
        <button onclick="setRange('1y')">1 Year</button>
        <button onclick="setRange('all')">All</button>
    </div>
    <div class="controls">
        <button onclick="navDate(-1)">&larr;</button>
        <input type="date" id="datePicker" onchange="goToDate()" />
        <button onclick="navDate(1)">&rarr;</button>
        <select id="dateSpan" onchange="goToDate()">
            <option value="1">1 Day</option>
            <option value="7">1 Week</option>
            <option value="30">1 Month</option>
            <option value="365">1 Year</option>
        </select>
        <button onclick="clearDatePicker()">Clear</button>
    </div>

    <div class="chart-section">
        <div class="checkboxes" id="chart1Checks">
            <span class="cb-group">Sensibo: <label><input type="checkbox" checked onchange="fetchAndPlot()" data-field="temperature" data-source="Sensibo"> Temp</label>
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="humidity" data-source="Sensibo"> Humidity</label></span>
            <span class="cb-group">Govee: <label><input type="checkbox" checked onchange="fetchAndPlot()" data-field="temperature" data-source="Govee"> Temp</label>
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="humidity" data-source="Govee"> Humidity</label></span>
            <span class="cb-group">Outside: <label><input type="checkbox" checked onchange="fetchAndPlot()" data-field="temperature" data-source="Weather"> Temp</label>
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="humidity" data-source="Weather"> Humidity</label></span>
        </div>
        <div class="chart" id="chart1" style="height:450px"></div>
    </div>

    <div class="chart-section">
        <div class="checkboxes" id="chart2Checks">
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="co2"> CO₂</label>
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="tvoc"> TVOC</label>
            <label><input type="checkbox" checked onchange="fetchAndPlot()" data-field="iaq"> AQI/IAQ</label>
        </div>
        <div class="chart" id="chart2" style="height:450px"></div>
    </div>

    <div class="chart-section">
        <div class="checkboxes" id="chart3Checks">
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="wind_speed"> Wind Speed</label>
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="wind_gust"> Wind Gust</label>
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="precip_rate"> Rain Rate</label>
            <label><input type="checkbox" checked onchange="fetchAndPlot()" data-field="precip_total"> Rain Total</label>
        </div>
        <div class="chart" id="chart3" style="height:450px"></div>
    </div>

    <div class="chart-section">
        <div class="checkboxes" id="chart4Checks">
            <label><input type="checkbox" checked onchange="fetchAndPlot()" data-field="pressure"> Pressure</label>
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="uv"> UV Index</label>
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="solar_radiation"> Solar Radiation</label>
        </div>
        <div class="chart" id="chart4" style="height:450px"></div>
    </div>

    <div class="chart-section">
        <div class="checkboxes" id="chart5Checks">
            <label><input type="checkbox" checked onchange="fetchAndPlot()" data-field="production_w"> Production (W)</label>
            <label><input type="checkbox" checked onchange="fetchAndPlot()" data-field="consumption_w"> Consumption (W)</label>
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="net_consumption_w"> Net (W)</label>
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="production_wh_today"> Prod Today (kWh)</label>
            <label><input type="checkbox" onchange="fetchAndPlot()" data-field="consumption_wh_today"> Cons Today (kWh)</label>
        </div>
        <div class="chart" id="chart5" style="height:450px"></div>
    </div>

    <script>
        const ROOM_COLORS = {
            'Outside': '#ffd93d',
            'Living Room': '#e94560',
            'Den': '#0f9b58',
            'Bedroom': '#4285f4',
            'Solar': '#fdcb6e'
        };

        const SOURCE_STYLES = {
            'Sensibo': 'solid',
            'Govee': 'dash',
            'Weather': 'solid',
            'Enphase': 'solid'
        };

        let currentRange = '24h';
        let customStart = null;
        let customEnd = null;

        function setRange(range) {
            currentRange = range;
            customStart = null;
            customEnd = null;
            document.getElementById('datePicker').value = '';
            document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            fetchAndPlot();
        }

        function goToDate() {
            let dateVal = document.getElementById('datePicker').value;
            if (!dateVal) return;
            let spanDays = parseInt(document.getElementById('dateSpan').value);
            let start = new Date(dateVal + 'T00:00:00');
            let end = new Date(start);
            end.setDate(end.getDate() + spanDays);
            customStart = start.toISOString();
            customEnd = end.toISOString();
            currentRange = 'custom';
            document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
            fetchAndPlot();
        }

        function navDate(direction) {
            let picker = document.getElementById('datePicker');
            let spanDays = parseInt(document.getElementById('dateSpan').value);
            let current = picker.value ? new Date(picker.value) : new Date();
            current.setDate(current.getDate() + (direction * spanDays));
            picker.value = current.toISOString().split('T')[0];
            goToDate();
        }

        function clearDatePicker() {
            document.getElementById('datePicker').value = '';
            customStart = null;
            customEnd = null;
            currentRange = '24h';
            document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
            document.querySelector('.controls button:nth-child(3)').classList.add('active');
            fetchAndPlot();
        }

        function parseKey(key) {
            let parts = key.split('|');
            return { room: parts[0], source: parts[1] };
        }

        const FIELD_CONFIG = {
            temperature: { label: 'Temp', unit: '°F', color: '#e94560' },
            humidity:    { label: 'Humidity', unit: '%', color: '#f5a623' },
            co2:         { label: 'CO₂', unit: 'ppm', color: '#e94560' },
            tvoc:        { label: 'TVOC', unit: 'ppb', color: '#0f9b58' },
            iaq:         { label: 'AQI/IAQ', unit: '', color: '#4285f4' },
            wind_speed:  { label: 'Wind', unit: 'mph', color: '#00cec9' },
            wind_gust:   { label: 'Gust', unit: 'mph', color: '#d63031' },
            precip_rate: { label: 'Rain Rate', unit: 'in/hr', color: '#74b9ff' },
            precip_total:{ label: 'Rain Total', unit: 'in', color: '#0984e3' },
            pressure:    { label: 'Pressure', unit: 'inHg', color: '#a29bfe' },
            uv:          { label: 'UV Index', unit: '', color: '#fdcb6e' },
            solar_radiation: { label: 'Solar', unit: 'W/m²', color: '#e17055' },
            production_w:    { label: 'Production', unit: 'W', color: '#fdcb6e' },
            consumption_w:   { label: 'Consumption', unit: 'W', color: '#e94560' },
            net_consumption_w: { label: 'Net', unit: 'W', color: '#00cec9' },
            production_wh_today: { label: 'Prod Today', unit: 'kWh', color: '#fdcb6e' },
            consumption_wh_today: { label: 'Cons Today', unit: 'kWh', color: '#e94560' }
        };

        function getCheckedFields(containerId) {
            let checks = document.querySelectorAll('#' + containerId + ' input[type=checkbox]');
            let fields = [];
            checks.forEach(cb => {
                if (cb.checked) {
                    fields.push({ field: cb.dataset.field, source: cb.dataset.source || null });
                }
            });
            return fields;
        }

        function fetchAndPlot() {
            let url = '/api/data?range=' + currentRange;
            if (customStart && customEnd) {
                url += '&start=' + encodeURIComponent(customStart) + '&end=' + encodeURIComponent(customEnd);
            }
            fetch(url)
                .then(r => r.json())
                .then(data => {
                    plotFiltered('chart1', data, getCheckedFields('chart1Checks'));
                    plotGeneric('chart2', data, getCheckedFields('chart2Checks'));
                    plotGeneric('chart3', data, getCheckedFields('chart3Checks'));
                    plotGeneric('chart4', data, getCheckedFields('chart4Checks'));
                    plotGeneric('chart5', data, getCheckedFields('chart5Checks'));
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

        // Source-aware chart: each checkbox specifies field + source
        function plotFiltered(divId, data, checks) {
            if (checks.length === 0) {
                Plotly.newPlot(divId, [], BASE_LAYOUT, { responsive: true });
                return;
            }
            let traces = [];
            let keys = Object.keys(data);
            let uniqueFields = [...new Set(checks.map(c => c.field))];
            let useSecondAxis = uniqueFields.length > 1;

            for (let key of keys) {
                let { room, source } = parseKey(key);
                let readings = data[key];
                let roomDash = SOURCE_STYLES[source] || 'solid';
                checks.forEach((check, i) => {
                    if (check.source && check.source !== source) return;
                    let field = check.field;
                    let hasData = readings.some(r => r[field] != null);
                    if (!hasData) return;
                    let cfg = FIELD_CONFIG[field];
                    let fieldIdx = uniqueFields.indexOf(field);
                    traces.push({
                        x: readings.map(r => r.timestamp),
                        y: readings.map(r => r[field]),
                        name: room + ' ' + source + ' ' + cfg.label,
                        type: 'scatter',
                        mode: 'lines',
                        line: { color: ROOM_COLORS[room] || '#fff', width: 2, dash: roomDash },
                        yaxis: (useSecondAxis && fieldIdx > 0) ? 'y2' : 'y'
                    });
                });
            }

            let firstCfg = FIELD_CONFIG[uniqueFields[0]];
            let yTitle = firstCfg.label + (firstCfg.unit ? ' (' + firstCfg.unit + ')' : '');
            let layout = Object.assign({}, BASE_LAYOUT, {
                yaxis: { title: yTitle, gridcolor: '#2a2a4a', side: 'left' }
            });

            if (useSecondAxis) {
                let otherLabels = uniqueFields.slice(1).map(f => {
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

        // Simple chart: checkboxes only specify field, all sources included
        function plotGeneric(divId, data, checks) {
            let fields = checks.map(c => c.field);
            if (fields.length === 0) {
                Plotly.newPlot(divId, [], BASE_LAYOUT, { responsive: true });
                return;
            }
            let traces = [];
            let keys = Object.keys(data);
            let useSecondAxis = fields.length > 1;

            // Check how many distinct rooms have data for these fields
            let roomsWithData = new Set();
            for (let key of keys) {
                let { room } = parseKey(key);
                let readings = data[key];
                if (fields.some(f => readings.some(r => r[f] != null))) {
                    roomsWithData.add(room);
                }
            }
            let singleRoom = roomsWithData.size === 1;

            for (let key of keys) {
                let { room, source } = parseKey(key);
                let readings = data[key];
                let roomDash = SOURCE_STYLES[source] || 'solid';
                fields.forEach((field, i) => {
                    let hasData = readings.some(r => r[field] != null);
                    if (!hasData) return;
                    let cfg = FIELD_CONFIG[field];
                    let color = singleRoom ? cfg.color : (ROOM_COLORS[room] || '#fff');
                    let name = singleRoom ? cfg.label : (room + ' ' + source + ' ' + cfg.label);
                    traces.push({
                        x: readings.map(r => r.timestamp),
                        y: readings.map(r => r[field]),
                        name: name,
                        type: 'scatter',
                        mode: 'lines',
                        line: { color: color, width: 2, dash: roomDash },
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

        function avg(arr, field) {
            let vals = arr.map(r => r[field]).filter(v => v != null);
            if (vals.length === 0) return null;
            return vals.reduce((a, b) => a + b, 0) / vals.length;
        }

        function fmtVal(v, decimals) {
            if (v == null) return '—';
            return v.toFixed(decimals);
        }

        function updateCurrentValues(data) {
            let isLatest = !customStart;
            let label = isLatest ? 'Latest' : 'Average';

            // Group by room, merge sources
            let rooms = {};
            let allFields = ['temperature','humidity','co2','tvoc','iaq',
                'wind_speed','wind_gust','precip_rate','precip_total','pressure','uv','solar_radiation'];
            let emptyVals = { timestamp: null };
            allFields.forEach(f => emptyVals[f] = null);

            for (let key of Object.keys(data)) {
                let { room, source } = parseKey(key);
                if (!rooms[room]) rooms[room] = {};
                let readings = data[key];
                if (readings.length === 0) {
                    rooms[room][source] = Object.assign({}, emptyVals);
                } else if (isLatest) {
                    rooms[room][source] = readings[readings.length - 1];
                } else {
                    let avgVals = { timestamp: readings[readings.length - 1].timestamp };
                    allFields.forEach(f => avgVals[f] = avg(readings, f));
                    rooms[room][source] = avgVals;
                }
            }

            // Sort: Outside first, then alphabetical
            let roomOrder = Object.keys(rooms).sort((a, b) => {
                let order = ['Outside', 'Solar'];
                let ai = order.indexOf(a), bi = order.indexOf(b);
                if (ai !== -1 && bi !== -1) return ai - bi;
                if (ai !== -1) return -1;
                if (bi !== -1) return -1;
                return a.localeCompare(b);
            });

            let html = '';
            let latestTime = '';
            for (let room of roomOrder) {
                let sources = rooms[room];
                let color = ROOM_COLORS[room] || '#fff';
                let metrics = '';
                for (let [source, vals] of Object.entries(sources)) {
                    if (vals.timestamp) latestTime = new Date(vals.timestamp).toLocaleString('en-US', { timeZone: 'America/Los_Angeles' });
                    let sourceLabel = vals.timestamp ? `${source} (${label})` : `${source} (No data)`;
                    metrics += `<div class="source-label">${sourceLabel}</div>`;
                    if (source !== 'Enphase') {
                        metrics += `<div class="metric"><span>Temp</span><span class="value">${fmtVal(vals.temperature, 1)}°F</span></div>`;
                        metrics += `<div class="metric"><span>Humidity</span><span class="value">${fmtVal(vals.humidity, 0)}%</span></div>`;
                    }
                    if (source === 'Sensibo') {
                        metrics += `<div class="metric"><span>CO₂</span><span class="value">${fmtVal(vals.co2, 0)} ppm</span></div>`;
                        metrics += `<div class="metric"><span>TVOC</span><span class="value">${fmtVal(vals.tvoc, 0)} ppb</span></div>`;
                        metrics += `<div class="metric"><span>AQI/IAQ</span><span class="value">${fmtVal(vals.iaq, 0)}</span></div>`;
                    }
                    if (source === 'Enphase') {
                        metrics += `<div class="metric"><span>Production</span><span class="value">${fmtVal(vals.production_w, 0)} W</span></div>`;
                        metrics += `<div class="metric"><span>Consumption</span><span class="value">${fmtVal(vals.consumption_w, 0)} W</span></div>`;
                        metrics += `<div class="metric"><span>Net</span><span class="value">${fmtVal(vals.net_consumption_w, 0)} W</span></div>`;
                        metrics += `<div class="metric"><span>Prod Today</span><span class="value">${fmtVal(vals.production_wh_today, 2)} kWh</span></div>`;
                        metrics += `<div class="metric"><span>Cons Today</span><span class="value">${fmtVal(vals.consumption_wh_today, 2)} kWh</span></div>`;
                    }
                    if (source === 'Weather') {
                        metrics += `<div class="metric"><span>AQI</span><span class="value">${fmtVal(vals.iaq, 0)}</span></div>`;
                        metrics += `<div class="metric"><span>Wind</span><span class="value">${fmtVal(vals.wind_speed, 1)} mph</span></div>`;
                        metrics += `<div class="metric"><span>Gust</span><span class="value">${fmtVal(vals.wind_gust, 1)} mph</span></div>`;
                        metrics += `<div class="metric"><span>Rain Rate</span><span class="value">${fmtVal(vals.precip_rate, 2)} in/hr</span></div>`;
                        metrics += `<div class="metric"><span>Rain Total</span><span class="value">${fmtVal(vals.precip_total, 2)} in</span></div>`;
                        metrics += `<div class="metric"><span>Pressure</span><span class="value">${fmtVal(vals.pressure, 2)} inHg</span></div>`;
                        metrics += `<div class="metric"><span>UV</span><span class="value">${fmtVal(vals.uv, 1)}</span></div>`;
                        metrics += `<div class="metric"><span>Solar</span><span class="value">${fmtVal(vals.solar_radiation, 0)} W/m²</span></div>`;
                    }
                }
                html += `
                    <div class="device-card" style="border-top: 3px solid ${color}">
                        <h3>${room}</h3>
                        ${metrics}
                    </div>
                `;
            }
            document.getElementById('currentValues').innerHTML = html;
            let timeLabel = isLatest ? 'Last reading: ' + latestTime : 'Showing average for selected range';
            document.getElementById('lastUpdate').textContent = timeLabel;
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
    from zoneinfo import ZoneInfo

    pacific = ZoneInfo("America/Los_Angeles")

    def to_pacific(ts_str):
        """Convert a UTC timestamp string to Pacific time ISO string."""
        if not ts_str:
            return ts_str
        ts_str = ts_str.replace("Z", "+00:00")
        try:
            dt = datetime.datetime.fromisoformat(ts_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(pacific).isoformat()
        except Exception:
            return ts_str

    range_param = request.args.get("range", "24h")
    start_param = request.args.get("start")
    end_param = request.args.get("end")
    now = datetime.datetime.utcnow()

    range_map = {
        "1h": datetime.timedelta(hours=1),
        "6h": datetime.timedelta(hours=6),
        "24h": datetime.timedelta(hours=24),
        "7d": datetime.timedelta(days=7),
        "30d": datetime.timedelta(days=30),
        "1y": datetime.timedelta(days=365),
    }

    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    def query_range(table, ts_col="timestamp"):
        if range_param == "custom" and start_param and end_param:
            return conn.execute(
                f"SELECT * FROM {table} WHERE {ts_col} >= ? AND {ts_col} < ? ORDER BY {ts_col}",
                (start_param, end_param),
            ).fetchall()
        elif range_param in range_map:
            since = (now - range_map[range_param]).isoformat() + "Z"
            return conn.execute(
                f"SELECT * FROM {table} WHERE {ts_col} >= ? ORDER BY {ts_col}",
                (since,),
            ).fetchall()
        else:
            return conn.execute(
                f"SELECT * FROM {table} ORDER BY {ts_col}"
            ).fetchall()

    rows = query_range("readings")
    govee_rows = query_range("govee_readings")
    weather_rows = query_range("weather_readings")
    solar_rows = query_range("solar_readings")

    # Pre-populate all known keys so cards always show
    all_rooms = conn.execute(
        "SELECT DISTINCT room_name FROM readings"
    ).fetchall()
    all_govee_rooms = conn.execute(
        "SELECT DISTINCT room_name FROM govee_readings"
    ).fetchall()
    has_weather = conn.execute(
        "SELECT 1 FROM weather_readings LIMIT 1"
    ).fetchone()
    has_solar = conn.execute(
        "SELECT 1 FROM solar_readings LIMIT 1"
    ).fetchone()

    conn.close()

    result = {}
    for row in all_rooms:
        result[row["room_name"] + "|Sensibo"] = []
    for row in all_govee_rooms:
        result[row["room_name"] + "|Govee"] = []
    if has_weather:
        result["Outside|Weather"] = []
    if has_solar:
        result["Solar|Enphase"] = []

    for row in rows:
        key = row["room_name"] + "|Sensibo"
        if key not in result:
            result[key] = []
        temp_c = row["temperature"]
        temp_f = round(temp_c * 9 / 5 + 32, 1) if temp_c is not None else None
        result[key].append(
            {
                "timestamp": to_pacific(row["timestamp"]),
                "temperature": temp_f,
                "humidity": row["humidity"],
                "co2": row["co2"],
                "tvoc": row["tvoc"],
                "iaq": row["iaq"],
            }
        )

    for row in govee_rows:
        key = row["room_name"] + "|Govee"
        if key not in result:
            result[key] = []
        temp_c = row["temperature"]
        temp_f = round(temp_c * 9 / 5 + 32, 1) if temp_c is not None else None
        result[key].append(
            {
                "timestamp": to_pacific(row["timestamp"]),
                "temperature": temp_f,
                "humidity": row["humidity"],
                "co2": None,
                "tvoc": None,
                "iaq": None,
            }
        )

    for row in weather_rows:
        key = "Outside|Weather"
        if key not in result:
            result[key] = []
        result[key].append(
            {
                "timestamp": to_pacific(row["timestamp"]),
                "temperature": row["temperature"],
                "humidity": row["humidity"],
                "co2": None,
                "tvoc": None,
                "iaq": row["aqi"],
                "wind_speed": row["wind_speed"],
                "wind_gust": row["wind_gust"],
                "pressure": row["pressure"],
                "precip_rate": row["precip_rate"],
                "precip_total": row["precip_total"],
                "uv": row["uv"],
                "solar_radiation": row["solar_radiation"],
            }
        )

    for row in solar_rows:
        key = "Solar|Enphase"
        if key not in result:
            result[key] = []
        prod_kwh = row["production_wh_today"]
        cons_kwh = row["consumption_wh_today"]
        result[key].append(
            {
                "timestamp": to_pacific(row["timestamp"]),
                "production_w": row["production_w"],
                "consumption_w": row["consumption_w"],
                "net_consumption_w": row["net_consumption_w"],
                "production_wh_today": round(prod_kwh / 1000, 2) if prod_kwh else None,
                "consumption_wh_today": round(cons_kwh / 1000, 2) if cons_kwh else None,
            }
        )

    return result


def main():
    init_db()
    init_govee_db()
    init_weather_db()
    init_solar_db()
    collector_thread = threading.Thread(target=run_collector, daemon=True)
    collector_thread.start()
    govee_thread = threading.Thread(target=run_govee_collector, daemon=True)
    govee_thread.start()
    weather_thread = threading.Thread(target=run_weather_collector, daemon=True)
    weather_thread.start()
    solar_thread = threading.Thread(target=run_solar_collector, daemon=True)
    solar_thread.start()
    print(f"\nDashboard running at http://localhost:{config.WEB_PORT}")
    app.run(host=config.WEB_HOST, port=config.WEB_PORT)


if __name__ == "__main__":
    main()
