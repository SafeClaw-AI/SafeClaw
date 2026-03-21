pub const ADAPTER_NAME: &str = "safeclaw-sqlite";

pub fn adapter_name() -> &'static str {
    ADAPTER_NAME
}

#[cfg(test)]
mod tests {
    use super::{adapter_name, ADAPTER_NAME};
    use rusqlite::Connection;

    #[test]
    fn adapter_crate_smoke_opens_sqlite_connection() {
        let conn = Connection::open_in_memory().expect("rusqlite must open in-memory db");
        let version: String = conn
            .query_row("SELECT sqlite_version()", [], |row| row.get(0))
            .expect("sqlite must answer version");

        assert_eq!(adapter_name(), ADAPTER_NAME);
        assert!(!version.is_empty());
    }
}
