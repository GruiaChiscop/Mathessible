use libmathcat::{
    do_navigate_command, errors_to_string, get_braille, get_navigation_braille,
    get_navigation_mathml_id, get_spoken_text, set_braille_user_signs, set_mathml,
    set_navigation_node, set_preference, set_rules_dir,
};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::ffi::{CString, c_char, c_int};
use std::sync::Mutex;

// MathCAT keeps all of its state in thread-locals, so each Python thread
// that calls in gets an independent instance. Every call releases the GIL
// (`py.detach`) so a worker thread can run MathCAT while the UI thread runs.

fn convert_error<T>(result: Result<T, libmathcat::errors::Error>) -> PyResult<T> {
    result.map_err(|error| PyRuntimeError::new_err(errors_to_string(&error)))
}

#[pyfunction]
#[pyo3(signature = (language="en", speech_style="SimpleSpeak", verbosity="Medium"))]
fn initialize(py: Python<'_>, language: &str, speech_style: &str, verbosity: &str) -> PyResult<()> {
    py.detach(|| {
        convert_error(set_rules_dir("Rules"))?;
        convert_error(set_preference("TTS", "none"))?;
        convert_error(set_preference("Language", language))?;
        convert_error(set_preference("SpeechStyle", speech_style))?;
        convert_error(set_preference("Verbosity", verbosity))?;
        convert_error(set_preference("Impairment", "Blindness"))?;
        Ok(())
    })
}

#[pyfunction]
fn preference(py: Python<'_>, name: &str, value: &str) -> PyResult<()> {
    py.detach(|| convert_error(set_preference(name, value)))
}

/// The user's own braille signs, as unicode.yaml entries (MathCAT patch 0008); "" clears them.
#[pyfunction]
fn braille_signs(py: Python<'_>, signs: &str) -> PyResult<()> {
    py.detach(|| convert_error(set_braille_user_signs(signs)))
}

#[pyfunction]
fn set_expression(py: Python<'_>, mathml: &str) -> PyResult<String> {
    py.detach(|| convert_error(set_mathml(mathml)))
}

#[pyfunction]
fn speak_expression(py: Python<'_>) -> PyResult<String> {
    py.detach(|| convert_error(get_spoken_text()))
}

#[pyfunction]
fn navigate(py: Python<'_>, command: &str) -> PyResult<String> {
    py.detach(|| convert_error(do_navigate_command(command)))
}

#[pyfunction]
fn navigation_id(py: Python<'_>) -> PyResult<(String, usize)> {
    py.detach(|| convert_error(get_navigation_mathml_id()))
}

#[pyfunction]
#[pyo3(signature = (node_id, offset=0))]
fn set_navigation(py: Python<'_>, node_id: &str, offset: usize) -> PyResult<()> {
    py.detach(|| convert_error(set_navigation_node(node_id, offset)))
}

#[pyfunction]
fn braille(py: Python<'_>, node_id: &str) -> PyResult<String> {
    py.detach(|| convert_error(get_braille(node_id)))
}

#[pyfunction]
fn navigation_braille(py: Python<'_>) -> PyResult<String> {
    py.detach(|| convert_error(get_navigation_braille()))
}

// liblouis (build.rs), for the document's text: widechar is 32 bits (UCS-4).
unsafe extern "system" {
    fn lou_translateString(
        table_list: *const c_char,
        inbuf: *const u32,
        inlen: *mut c_int,
        outbuf: *mut u32,
        outlen: *mut c_int,
        typeform: *mut u16,
        spacing: *mut c_char,
        mode: c_int,
    ) -> c_int;
}

// liblouis keeps its compiled tables in globals and is not thread-safe.
static LOUIS: Mutex<()> = Mutex::new(());
const DOTS_IO: c_int = 4;
const UC_BRL: c_int = 64;

/// `text` in braille by the liblouis `table` (a full path, or a comma-separated list), as Unicode braille cells.
#[pyfunction]
fn text_braille(py: Python<'_>, table: &str, text: &str) -> PyResult<String> {
    let table = CString::new(table).map_err(|_| PyRuntimeError::new_err("the table path holds a NUL"))?;
    let input: Vec<u32> = text.chars().map(u32::from).collect();
    py.detach(|| {
        let _guard = LOUIS.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        let mut capacity = input.len() * 4 + 64;
        loop {
            let mut output = vec![0u32; capacity];
            let mut inlen = input.len() as c_int;
            let mut outlen = capacity as c_int;
            let ok = unsafe {
                lou_translateString(
                    table.as_ptr(),
                    input.as_ptr(),
                    &mut inlen,
                    output.as_mut_ptr(),
                    &mut outlen,
                    std::ptr::null_mut(),
                    std::ptr::null_mut(),
                    DOTS_IO | UC_BRL,
                )
            };
            if ok == 0 {
                return Err(PyRuntimeError::new_err("liblouis could not translate with this table"));
            }
            if (inlen as usize) < input.len() {
                capacity *= 2; // The output filled up before the input ended.
                continue;
            }
            output.truncate(outlen as usize);
            return Ok(output.into_iter().filter_map(char::from_u32).collect());
        }
    })
}

#[pymodule]
fn mathessible_mathcat(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(initialize, module)?)?;
    module.add_function(wrap_pyfunction!(text_braille, module)?)?;
    module.add_function(wrap_pyfunction!(preference, module)?)?;
    module.add_function(wrap_pyfunction!(braille_signs, module)?)?;
    module.add_function(wrap_pyfunction!(set_expression, module)?)?;
    module.add_function(wrap_pyfunction!(speak_expression, module)?)?;
    module.add_function(wrap_pyfunction!(navigate, module)?)?;
    module.add_function(wrap_pyfunction!(navigation_id, module)?)?;
    module.add_function(wrap_pyfunction!(set_navigation, module)?)?;
    module.add_function(wrap_pyfunction!(braille, module)?)?;
    module.add_function(wrap_pyfunction!(navigation_braille, module)?)?;
    Ok(())
}

