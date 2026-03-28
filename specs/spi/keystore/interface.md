# KeyStore 抽象层接口

## 目的
- 为 SafeClaw 预留统一的密钥存取抽象层。
- 当前仅定义接口边界，不实现任何真实功能。
- 未来可无缝接入软件密钥、硬件密钥与云 KMS。

## 接口标识
- abstraction_id: `keystore`
- spi_family: `security-abstraction`
- current_mode: `reserved-interface-only`

## 输入
- `spi_version`: 接口版本，SemVer
- `request_id`: 调用唯一标识
- `operation`: `create` | `load` | `sign` | `verify` | `encrypt` | `decrypt` | `destroy`
- `key_ref`: 逻辑密钥引用，不暴露底层实现细节
- `algorithm`: 算法标识，如 `ed25519`、`rsa-4096`、`aes-256-gcm`
- `payload`: 待处理数据或参数对象
- `metadata`: 可选上下文，如用途、租户、环境、过期时间
- `timeout_ms`: 超时时间

## 输出
- `ok`: 是否成功
- `provider`: 当前提供者标识
- `key_handle`: 可返回的逻辑句柄
- `result`: 签名、密文、明文或元信息
- `attestation`: 可选证明材料
- `error`: 失败时的错误对象

## 未来模块预留
- TPM
- Secure Enclave
- Intel SGX
- AMD SEV
- 云厂商 KMS
