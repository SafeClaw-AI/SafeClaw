use std::{error::Error, fmt};

#[derive(Debug)]
pub enum SqliteAdapterError {
    Sqlite(rusqlite::Error),
    InvalidPragmaValue { pragma: &'static str, value: String },
    InvalidStoredValue { field: &'static str, value: String },
    IntegerOutOfRange { field: &'static str, value: i64 },
    UnsupportedSchemaVersion { current: i64, expected: i64 },
}

impl fmt::Display for SqliteAdapterError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Sqlite(error) => write!(f, "sqlite adapter error: {error}"),
            Self::InvalidPragmaValue { pragma, value } => {
                write!(
                    f,
                    "sqlite pragma {pragma} returned unexpected value {value}"
                )
            }
            Self::InvalidStoredValue { field, value } => {
                write!(
                    f,
                    "sqlite stored field {field} returned unexpected value {value}"
                )
            }
            Self::IntegerOutOfRange { field, value } => {
                write!(
                    f,
                    "sqlite stored field {field} returned out-of-range integer {value}"
                )
            }
            Self::UnsupportedSchemaVersion { current, expected } => write!(
                f,
                "sqlite schema version {current} is unsupported, expected {expected}"
            ),
        }
    }
}

impl Error for SqliteAdapterError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::Sqlite(error) => Some(error),
            Self::InvalidPragmaValue { .. }
            | Self::InvalidStoredValue { .. }
            | Self::IntegerOutOfRange { .. }
            | Self::UnsupportedSchemaVersion { .. } => None,
        }
    }
}

impl From<rusqlite::Error> for SqliteAdapterError {
    fn from(value: rusqlite::Error) -> Self {
        Self::Sqlite(value)
    }
}
