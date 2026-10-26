use libmathcat::{
    do_navigate_command, errors_to_string, get_braille, get_navigation_braille,
    get_navigation_mathml_id, get_spoken_text, set_braille_user_signs, set_mathml,
    set_navigation_node, set_preference, set_rules_dir,
};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

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

#[pymodule]
fn mathessible_mathcat(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(initialize, module)?)?;
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

