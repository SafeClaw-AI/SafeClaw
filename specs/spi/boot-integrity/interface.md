# Boot Integrity 抽象层接口

## 目的
- 为 SafeClaw 预留统一的启动完整性校验抽象层。
- 当前仅定义接口边界，不实现任何真实功能。
- 未来可对接软件校验链、Secure Boot、远程证明与硬件信任根。

## 接口标识
- abstraction_id: `boot-integrity`
- spi_family: `security-abstraction`
- current_mode: `reserved-interface-only`

## 输入
- `spi_version`: 接口版本，SemVer
- `request_id`: 调用唯一标识
- `operation`: `measure` | `verify` | `attest`
- `boot_artifacts`: 启动链组件摘要、路径或测量集合
- `policy_ref`: 校验策略引用
- `environment`: 运行环境信息
- `timeout_ms`: 超时时间

## 输出
- `ok`: 是否成功
- `provider`: 当前提供者标识
- `integrity_state`: `trusted` | `warning` | `untrusted`
- `measurements`: 测量结果集合
- `attestation`: 可选证明材料
- `error`: 失败时的错误对象

## 未来模块预留
- Secure Boot
- TPM PCR 校验
- Intel TXT / SGX 证明
- AMD SEV 证明
- 云厂商启动完整性服务
