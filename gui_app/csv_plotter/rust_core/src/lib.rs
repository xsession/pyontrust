use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;
use std::fs;

#[derive(thiserror::Error, Debug)]
enum CoreError {
    #[error("invalid input: {0}")]
    InvalidInput(String),
    #[error("io error: {0}")]
    Io(String),
    #[error("csv error: {0}")]
    Csv(String),
}

impl From<CoreError> for PyErr {
    fn from(value: CoreError) -> Self {
        PyValueError::new_err(value.to_string())
    }
}

fn sniff_delimiter(path: &str) -> Result<u8, CoreError> {
    let data = fs::read(path).map_err(|e| CoreError::Io(e.to_string()))?;
    let sample = if data.len() > 64 * 1024 {
        &data[..64 * 1024]
    } else {
        &data
    };

    let text = String::from_utf8_lossy(sample);
    let first_line = text.lines().next().unwrap_or("");

    let candidates: &[(u8, char)] = &[(b',', ','), (b';', ';'), (b'\t', '\t'), (b'|', '|')];
    let mut best = (b',', 0usize);
    for (b, ch) in candidates {
        let n = first_line.chars().filter(|c| c == ch).count();
        if n > best.1 {
            best = (*b, n);
        }
    }

    Ok(best.0)
}

fn read_header_impl(path: &str) -> Result<Vec<String>, CoreError> {
    let delim = sniff_delimiter(path)?;
    let mut rdr = csv::ReaderBuilder::new()
        .delimiter(delim)
        .has_headers(true)
        .flexible(true)
        .from_path(path)
        .map_err(|e| CoreError::Csv(e.to_string()))?;

    let hdr = rdr
        .headers()
        .map_err(|e| CoreError::Csv(e.to_string()))?
        .iter()
        .map(|s| s.to_string())
        .collect::<Vec<_>>();

    Ok(hdr)
}

#[pyfunction]
fn read_csv_header(path: &str) -> PyResult<Vec<String>> {
    if path.trim().is_empty() {
        return Err(CoreError::InvalidInput("path is empty".into()).into());
    }
    read_header_impl(path).map_err(Into::into)
}

fn median_sorted(sorted: &[f64]) -> f64 {
    if sorted.is_empty() {
        return f64::NAN;
    }
    let n = sorted.len();
    if n % 2 == 1 {
        sorted[n / 2]
    } else {
        0.5 * (sorted[n / 2 - 1] + sorted[n / 2])
    }
}

#[pyfunction]
fn read_xy_decimated<'py>(
    py: Python<'py>,
    path: &str,
    x_col: &str,
    y_cols: Vec<String>,
    max_points: usize,
) -> PyResult<Bound<'py, PyDict>> {
    if path.trim().is_empty() {
        return Err(CoreError::InvalidInput("path is empty".into()).into());
    }
    if x_col.trim().is_empty() {
        return Err(CoreError::InvalidInput("x_col is empty".into()).into());
    }
    if y_cols.is_empty() {
        return Err(CoreError::InvalidInput("y_cols is empty".into()).into());
    }

    let delim = sniff_delimiter(path)?;
    let mut rdr = csv::ReaderBuilder::new()
        .delimiter(delim)
        .has_headers(true)
        .flexible(true)
        .from_path(path)
        .map_err(|e| CoreError::Csv(e.to_string()))?;

    let headers = rdr
        .headers()
        .map_err(|e| CoreError::Csv(e.to_string()))?
        .iter()
        .map(|s| s.to_string())
        .collect::<Vec<_>>();

    let mut idx: HashMap<String, usize> = HashMap::with_capacity(headers.len());
    for (i, h) in headers.iter().enumerate() {
        idx.insert(h.clone(), i);
    }

    let xi = idx
        .get(x_col)
        .copied()
        .ok_or_else(|| CoreError::InvalidInput(format!("x column '{x_col}' not found")))?;

    let mut yi: Vec<(String, usize)> = Vec::with_capacity(y_cols.len());
    for c in y_cols.iter() {
        let k = idx
            .get(c)
            .copied()
            .ok_or_else(|| CoreError::InvalidInput(format!("y column '{c}' not found")))?;
        yi.push((c.clone(), k));
    }

    let mut x: Vec<f64> = Vec::new();
    let mut ys: HashMap<String, Vec<f64>> = HashMap::with_capacity(yi.len());
    for (name, _) in yi.iter() {
        ys.insert(name.clone(), Vec::new());
    }

    let mut stats_acc: HashMap<String, Vec<f64>> = HashMap::with_capacity(yi.len());
    for (name, _) in yi.iter() {
        stats_acc.insert(name.clone(), Vec::new());
    }

    for rec in rdr.records() {
        let rec = rec.map_err(|e| CoreError::Csv(e.to_string()))?;
        let xv = rec.get(xi).unwrap_or("");
        let xv = match xv.trim().parse::<f64>() {
            Ok(v) => v,
            Err(_) => continue,
        };

        x.push(xv);
        for (name, k) in yi.iter() {
            let s = rec.get(*k).unwrap_or("");
            let v = s.trim().parse::<f64>().unwrap_or(f64::NAN);
            ys.get_mut(name).unwrap().push(v);
            if v.is_finite() {
                stats_acc.get_mut(name).unwrap().push(v);
            }
        }
    }

    let n = x.len();
    if n == 0 {
        return Err(CoreError::InvalidInput("no numeric rows found".into()).into());
    }

    // Decimate for plotting
    let max_points = max_points.max(10);
    let step = ((n as f64) / (max_points as f64)).ceil() as usize;
    let step = step.max(1);

    let mut x_d: Vec<f64> = Vec::with_capacity((n + step - 1) / step);
    for i in (0..n).step_by(step) {
        x_d.push(x[i]);
    }

    let mut ys_d: HashMap<String, Vec<f64>> = HashMap::with_capacity(ys.len());
    for (name, v) in ys.iter() {
        let mut out = Vec::with_capacity((n + step - 1) / step);
        for i in (0..n).step_by(step) {
            out.push(v[i]);
        }
        ys_d.insert(name.clone(), out);
    }

    // Stats (computed on finite raw samples)
    let stats = PyDict::new_bound(py);
    for (name, vals) in stats_acc.iter_mut() {
        if vals.is_empty() {
            continue;
        }
        let mut mn = f64::INFINITY;
        let mut mx = f64::NEG_INFINITY;
        let mut sum = 0.0f64;
        for &v in vals.iter() {
            if v < mn {
                mn = v;
            }
            if v > mx {
                mx = v;
            }
            sum += v;
        }
        let mean = sum / (vals.len() as f64);
        vals.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let med = median_sorted(vals);
        let d = PyDict::new_bound(py);
        d.set_item("min", mn)?;
        d.set_item("max", mx)?;
        d.set_item("mean", mean)?;
        d.set_item("median", med)?;
        d.set_item("p2p", mx - mn)?;
        stats.set_item(name, d)?;
    }

    let series = PyDict::new_bound(py);
    for (name, v) in ys_d.iter() {
        series.set_item(name, v.clone())?;
    }

    let out = PyDict::new_bound(py);
    out.set_item("x", x_d)?;
    out.set_item("series", series)?;
    out.set_item("stats", stats)?;
    out.set_item("row_count", n)?;
    Ok(out)
}

#[pymodule]
fn pyontrust_csv_plotter_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(read_csv_header, m)?)?;
    m.add_function(wrap_pyfunction!(read_xy_decimated, m)?)?;
    Ok(())
}
