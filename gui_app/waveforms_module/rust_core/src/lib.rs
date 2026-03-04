use numpy::{IntoPyArray, PyArray1, PyReadonlyArray1};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rustfft::{num_complex::Complex32, FftPlanner};

#[derive(thiserror::Error, Debug)]
enum CoreError {
    #[error("invalid input: {0}")]
    InvalidInput(String),
}

impl From<CoreError> for PyErr {
    fn from(value: CoreError) -> Self {
        PyValueError::new_err(value.to_string())
    }
}

fn window(kind: &str, n: usize) -> Result<Vec<f32>, CoreError> {
    if n == 0 {
        return Ok(vec![]);
    }
    match kind {
        "hann" | "hanning" => {
            let mut w = vec![0.0f32; n];
            let m = (n - 1) as f32;
            for (i, wi) in w.iter_mut().enumerate() {
                *wi = 0.5 - 0.5 * (2.0 * std::f32::consts::PI * (i as f32) / m).cos();
            }
            Ok(w)
        }
        "blackman" => {
            let mut w = vec![0.0f32; n];
            let m = (n - 1) as f32;
            for (i, wi) in w.iter_mut().enumerate() {
                let a0 = 0.42;
                let a1 = 0.5;
                let a2 = 0.08;
                let x = 2.0 * std::f32::consts::PI * (i as f32) / m;
                *wi = a0 - a1 * x.cos() + a2 * (2.0 * x).cos();
            }
            Ok(w)
        }
        "flattop" => {
            // Common 5-term flattop coefficients
            let mut w = vec![0.0f32; n];
            let m = (n - 1) as f32;
            let a0 = 1.0;
            let a1 = 1.93;
            let a2 = 1.29;
            let a3 = 0.388;
            let a4 = 0.028;
            for (i, wi) in w.iter_mut().enumerate() {
                let x = 2.0 * std::f32::consts::PI * (i as f32) / m;
                *wi = a0
                    - a1 * x.cos()
                    + a2 * (2.0 * x).cos()
                    - a3 * (3.0 * x).cos()
                    + a4 * (4.0 * x).cos();
            }
            Ok(w)
        }
        other => Err(CoreError::InvalidInput(format!("unknown window '{other}'"))),
    }
}

#[pyfunction]
fn decimate_envelope<'py>(
    py: Python<'py>,
    samples: PyReadonlyArray1<'py, f32>,
    out_len: usize,
) -> PyResult<(Bound<'py, PyArray1<f32>>, Bound<'py, PyArray1<f32>>)> {
    let s = samples.as_array();
    let n = s.len();
    let out_len = out_len.max(1);

    let mut lo = vec![0.0f32; out_len];
    let mut hi = vec![0.0f32; out_len];
    if n == 0 {
        return Ok((lo.into_pyarray_bound(py), hi.into_pyarray_bound(py)));
    }

    for i in 0..out_len {
        let a = (i * n) / out_len;
        let b = ((i + 1) * n) / out_len;
        let b = b.max(a + 1);
        let seg = s.slice(ndarray::s![a..b.min(n)]);
        let mut minv = f32::INFINITY;
        let mut maxv = f32::NEG_INFINITY;
        for &v in seg.iter() {
            if v < minv {
                minv = v;
            }
            if v > maxv {
                maxv = v;
            }
        }
        lo[i] = minv;
        hi[i] = maxv;
    }

    Ok((lo.into_pyarray_bound(py), hi.into_pyarray_bound(py)))
}

#[pyfunction]
fn measure_basic<'py>(
    _py: Python<'py>,
    samples: PyReadonlyArray1<'py, f32>,
    _sample_rate_hz: f64,
) -> PyResult<std::collections::HashMap<&'static str, Option<f64>>> {
    let s = samples.as_array();
    if s.len() == 0 {
        return Ok([
            ("vpp", Some(0.0)),
            ("vmin", Some(0.0)),
            ("vmax", Some(0.0)),
            ("mean", Some(0.0)),
            ("vrms", Some(0.0)),
            ("frequency_hz", None),
        ]
        .into_iter()
        .collect());
    }
    let mut vmin = f32::INFINITY;
    let mut vmax = f32::NEG_INFINITY;
    let mut sum = 0.0f64;
    let mut sumsq = 0.0f64;
    for &v in s.iter() {
        if v < vmin {
            vmin = v;
        }
        if v > vmax {
            vmax = v;
        }
        sum += v as f64;
        sumsq += (v as f64) * (v as f64);
    }
    let n = s.len() as f64;
    let mean = sum / n;
    let vrms = (sumsq / n).sqrt();
    let vpp = (vmax - vmin) as f64;

    Ok([
        ("vpp", Some(vpp)),
        ("vmin", Some(vmin as f64)),
        ("vmax", Some(vmax as f64)),
        ("mean", Some(mean)),
        ("vrms", Some(vrms)),
        ("frequency_hz", None),
    ]
    .into_iter()
    .collect())
}

#[pyfunction]
fn fft_spectrum<'py>(
    py: Python<'py>,
    samples: PyReadonlyArray1<'py, f32>,
    sample_rate_hz: f64,
    window_kind: &str,
) -> PyResult<std::collections::HashMap<&'static str, Bound<'py, PyArray1<f32>>>> {
    let s = samples.as_array();
    let n = s.len();
    if n < 2 {
        let freq = vec![0.0f32].into_pyarray_bound(py);
        let mag = vec![0.0f32].into_pyarray_bound(py);
        let mut out = std::collections::HashMap::with_capacity(2);
        out.insert("freq_hz", freq);
        out.insert("mag", mag);
        return Ok(out);
    }

    let w = window(window_kind, n)?;
    let mut buf: Vec<Complex32> = s
        .iter()
        .zip(w.iter())
        .map(|(&x, &wi)| Complex32::new(x * wi, 0.0))
        .collect();

    let mut planner = FftPlanner::<f32>::new();
    let fft = planner.plan_fft_forward(n);
    fft.process(&mut buf);

    let out_n = n / 2 + 1;
    let mut freq = vec![0.0f32; out_n];
    let mut mag = vec![0.0f32; out_n];
    let sr = sample_rate_hz as f32;
    let norm = (n as f32).max(1.0);
    for k in 0..out_n {
        freq[k] = (k as f32) * sr / (n as f32);
        mag[k] = buf[k].norm() / norm;
    }

    let mut out = std::collections::HashMap::with_capacity(2);
    out.insert("freq_hz", freq.into_pyarray_bound(py));
    out.insert("mag", mag.into_pyarray_bound(py));
    Ok(out)
}

#[pyfunction]
fn find_edge_trigger(
    samples: PyReadonlyArray1<'_, f32>,
    level: f32,
    hysteresis: f32,
    edge: &str,
) -> PyResult<Option<usize>> {
    let s = samples.as_array();
    if s.len() < 2 {
        return Ok(None);
    }
    let h = hysteresis.abs().max(1e-9);
    let lo = level - h;
    let hi = level + h;

    match edge {
        "rising" => {
            let mut armed = false;
            for i in 1..s.len() {
                let prev = s[i - 1];
                let cur = s[i];
                if !armed {
                    if prev <= lo {
                        armed = true;
                    }
                    continue;
                }
                if prev < hi && cur >= hi {
                    return Ok(Some(i));
                }
            }
            Ok(None)
        }
        "falling" => {
            let mut armed = false;
            for i in 1..s.len() {
                let prev = s[i - 1];
                let cur = s[i];
                if !armed {
                    if prev >= hi {
                        armed = true;
                    }
                    continue;
                }
                if prev > lo && cur <= lo {
                    return Ok(Some(i));
                }
            }
            Ok(None)
        }
        other => Err(CoreError::InvalidInput(format!("unknown edge '{other}'")))?,
    }
}

#[pymodule]
fn pyontrust_waveforms_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(decimate_envelope, m)?)?;
    m.add_function(wrap_pyfunction!(measure_basic, m)?)?;
    m.add_function(wrap_pyfunction!(fft_spectrum, m)?)?;
    m.add_function(wrap_pyfunction!(find_edge_trigger, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use approx::assert_relative_eq;

    #[test]
    fn envelope_basic() {
        let s = vec![0.0f32, 1.0, -1.0, 0.5, 2.0, -2.0];
        let n = s.len();
        let out_len = 3;
        let mut lo = vec![0.0f32; out_len];
        let mut hi = vec![0.0f32; out_len];
        for i in 0..out_len {
            let a = (i * n) / out_len;
            let b = ((i + 1) * n) / out_len;
            let b = b.max(a + 1);
            let seg = &s[a..b.min(n)];
            let mut minv = f32::INFINITY;
            let mut maxv = f32::NEG_INFINITY;
            for &v in seg {
                minv = minv.min(v);
                maxv = maxv.max(v);
            }
            lo[i] = minv;
            hi[i] = maxv;
        }
        assert_relative_eq!(lo[0], 0.0);
        assert_relative_eq!(hi[0], 1.0);
    }
}
