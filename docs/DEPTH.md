# 深度登记 农产品残留限量版本与复检裁决

规模：中型。核心规则：按采样日期选择有效限量，低于检出限保留区间；复检不得越过样本关联与方法适用范围。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 报告采信 | 查看并复算报告采信 | `/api/m1_ingest` | `app/modules/m1_ingest/reader.py` | `tests/test_ingest.py` |
| M2 项目映射 | 查看并复算项目映射 | `/api/m2_mapping` | `app/modules/m2_mapping/rules.py` | `tests/test_mapping.py` |
| M3 限量选版 | 查看并复算限量选版 | `/api/m3_versions` | `app/modules/m3_versions/rules.py` | `tests/test_versions.py` |
| M4 检出量换算 | 查看并复算检出量换算 | `/api/m4_segments` | `app/modules/m4_segments/rules.py` | `tests/test_segments.py` |
| M5 复检裁决 | 查看并复算复检裁决 | `/api/m5_calculate` | `app/modules/m5_calculate/rules.py` | `tests/test_calculate.py` |
| M6 批次判级 | 查看并复算批次判级 | `/api/m6_reconcile` | `app/modules/m6_reconcile/compare.py` | `tests/test_reconcile.py` |
| M7 报告归档 | 查看并复算报告归档 | `/api/m7_archive` | `app/modules/m7_archive/export_out.py` | `tests/test_archive.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现 | 处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | GB18030中文 | 固定UTF-8失败 | 按编码链回退 | `app/modules/m1_ingest/decode.py` | `tests/test_ingest.py::test_legacy_encoding` |
| TRAP-02 | 表头BOM | 首列键失配 | 去除BOM | `app/modules/m1_ingest/decode.py` | `tests/test_ingest.py::test_bom` |
| TRAP-03 | 引号内换行 | 分行误计 | csv逻辑记录 | `app/modules/m1_ingest/reader.py` | `tests/test_ingest.py::test_preserves_multiline_note` |
| TRAP-05 | 列数错位 | 静默补列 | WIDTH隔离 | `app/modules/m1_ingest/reader.py` | `tests/test_ingest.py::test_width_isolation` |
| TRAP-06 | 全角千分位 | float失败 | NFKC与Decimal | `app/modules/m2_mapping/coerce.py` | `tests/test_mapping.py::test_thousands` |
| TRAP-07 | 空值哨兵 | 空值当零 | MISSING隔离 | `app/modules/m2_mapping/coerce.py` | `tests/test_mapping.py::test_missing_numeric` |
| TRAP-08 | 前导零ID | 编码失真 | 字符串保形 | `app/modules/m2_mapping/rules.py` | `tests/test_mapping.py::test_identifier_zeroes` |
| TRAP-10 | 浮点误差 | 累计失准 | Decimal求和 | `app/modules/m2_mapping/coerce.py` | `tests/test_mapping.py::test_decimal_precision` |
| TRAP-14 | 同版冲突 | 最后覆盖 | 整组隔离 | `app/modules/m2_mapping/rules.py` | `tests/test_mapping.py::test_real_conflict_quarantine` |
| TRAP-18 | 三种空态 | 除零或伪成功 | 三个错误码 | `app/modules/m1_ingest/reader.py` | `tests/test_ingest.py::test_empty_three_states` |
| TRAP-26 | 旧版本复核 | 覆盖新结论 | 事务条件更新 | `app/store.py` | `tests/test_archive.py::test_stale_review` |
| TRAP-15 | ug/kg与mg/kg | 差1000倍 | 浓度统一mg/kg，单位写法归一 | `app/modules/m4_segments/units.py` | `tests/test_segments.py::test_unit_conversion`、`test_unit_spellings_resolve_to_same_scale` |
| TRAP-27 | 原检复检跨单位 | 按各自字面单位判级/要求单位写法一致才接入 | 折算mg/kg后比较统一区间 | `app/modules/m4_segments/units.py`、`app/modules/m5_calculate/rules.py` | `tests/test_calculate.py::test_cross_unit_retest_supports_one_conclusion`、`test_equal_interval_after_unit_conversion_is_not_conflict` |
| TRAP-28 | 并列复检矛盾 | 整组丢弃或覆盖旧结论 | 采信失败以 SUPERSEDE 隔离矛盾复检、保留旧版结论并沿用其区间 | `app/modules/m5_calculate/rules.py`、`app/modules/m6_reconcile/compare.py` | `tests/test_calculate.py::test_adoption_failure_retains_previous_conclusion` |
| TRAP-29 | 封存证据缺原始报告/隔离原因 | 仅导出结论 | 证据含原始报告、跨单位支撑与隔离原因 | `app/modules/m7_archive/export_out.py` | `tests/test_archive.py::test_archive_keeps_original_reports_and_isolation_reasons` |
| TRAP-30 | 同源重跑 | 新增记录或改换已确认结论 | 幂等保存，已存结论不被替换 | `app/store.py` | `tests/test_archive.py::test_rerun_same_source_keeps_recorded_conclusion` |
| TRAP-25 | 标准时间边界 | 双版或错版 | 采样日半开区间选版 | `app/modules/m3_versions/standards.py` | `tests/test_versions.py::test_halfopen_effective` |
| TRAP-20 | 复检引用环 | 遍历无法结束 | 引用路径检测 | `app/modules/m5_calculate/rules.py` | `tests/test_calculate.py::test_cycle_rejected` |

## 对账规则

输入行数=采纳+隔离+空行+重复表头+完全重复；业务总数与计算证据独立求和。隔离行保留来源行、ID、原因码与原值。

## 已知不覆盖

不做多租户权限和外部服务联调。行业规则以项目数据字典为准。文件上限2MB，逐行解析后在上限内完成分组计算。
