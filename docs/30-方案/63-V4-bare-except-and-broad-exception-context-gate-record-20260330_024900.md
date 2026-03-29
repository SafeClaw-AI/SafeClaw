# V4 bare except and broad exception context gate record

- 时间：2026-03-30 02:49:00 +0800
- 轮次：M1b Slice 191
- 目标：把 `check_reference_redlines.py` 里已存在但未合同化的“裸 `except` / broad `Exception` 必须保留上下文”语义收成明确红线；让报错更可执行，避免后续新增宽泛异常兜底时悄悄绕过上下文要求。

## 本轮动作
- 调整 `tools/checks/check_reference_redlines.py` 的 `_handler_context_requirement()`：当命中裸 `except:` 时，不再复用笼统的 broad except 提示，而是明确报错“裸 except 不允许；必须显式捕获异常类型并绑定 `as error`”。
- 在 `tests/contracts/test_reference_redlines_check.py` 新增 3 条合同：锁住裸 `except:` 必须失败、`except Exception:` 未绑定必须失败、`except Exception as error:` 且真实使用上下文时必须通过。
- 保持运行时代码零改动；当前基线里唯一 `except Exception as error` 现场已天然合规，本轮专注把隐含门禁补成可回归合同。

## 结果
- reference 红线现在对“多异常 / 指定高风险异常 / broad Exception / 裸 except”四类场景都有明确可回归合同。
- 未来若有人写出 `except:` 或 `except Exception:` 且不保留上下文，会直接被 fail-closed 拦住，不再依赖人工 code review 记忆。

## 验证
- `python -m py_compile tools/checks/check_reference_redlines.py tests/contracts/test_reference_redlines_check.py`
- `python -m unittest tests.contracts.test_reference_redlines_check -v`
- `python tools/checks/check_reference_redlines.py`
- `python tools/checks/check_ledger_alignment.py`
- `git diff --check`

## 下一步
- 继续沿 `docs/reference/01` 扩 reference fail-closed 门禁；优先评估下一组“静默降级异常形态”或更可落地的复杂度红线，不回头重复做说明层小修。