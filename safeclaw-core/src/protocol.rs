pub const PROTOCOL_VERSION_ANCHOR: &str =
    include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/../VERSION"));

pub fn protocol_version() -> &'static str {
    PROTOCOL_VERSION_ANCHOR.trim()
}
