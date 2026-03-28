# Storage Encryption 抽象层接口

## 目的
- 为 SafeClaw 预留统一的存储加密抽象层。
- 当前仅定义接口边界，不实现任何真实功能。
- 未来可接软件加密、磁盘硬件加密、机密计算内存封装与云密钥托管。

## 接口标识
- abstraction_id: `storage-encryption`
- spi_family: `security-abstraction`
- current_mode: `reserved-interface-only`

## 输入
- `spi_version`: 接口版本，SemVer
- `request_id`: 调用唯一标识
- `operation`: `encrypt` | `decrypt` | `rotate-key` | `inspect`
- `resource_ref`: 目标资源引用，如文件、卷、数据库或对象存储路径
- `key_ref`: 逻辑密钥引用
- `policy_ref`: 加密策略引用
- `payload`: 待处理数据或参数对象
- `timeout_ms`: 超时时间

## 输出
- `ok`: 是否成功
- `provider`: 当前提供者标识
- `cipher_state`: `plaintext` | `encrypted` | `rotated`
- `result`: 结果对象或数据
- `attestation`: 可选证明材料
- `error`: 失败时的错误对象

## 未来模块预留
- TPM 绑定密钥
- Secure Enclave 密钥代理
- Intel SGX 密钥封装
- AMD SEV 机密内存辅助
- 云厂商 KMS / EKM
