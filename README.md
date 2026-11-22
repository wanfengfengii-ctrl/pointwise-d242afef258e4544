# 衡岬计量室双台架比测

衡岬计量室白班从设备导出整数显示并取得量程核定单。夜班在两台架停源后签发差值，晨班凭定稿和实收出处安排复测。工作台使用 Python 3.11 标准库及 SQLite。每站有自己的库，隔离台有单独的库。

## 运行

```sh
python3 -B check_project.py
python3 -B -m workbench demo
```

控制台随项目提供 `check_project.py`，它运行完整的 `tests` 回归。也可直接运行 `python3 -B -m unittest discover`。演示在临时目录载入 `samples/day.json`、`samples/night.json` 和 `samples/morning.json`，实收两站来件后关闭站库并签第一份定稿。乙站勘误后重新发行，夜班签第二份定稿。演示重开隔离库后按号领取两份定稿和回执。

## 工作流程和公开入口

调用方使用 `sqlite3.connect(path)` 打开工作库。`workbench.initialize_station(db)` 和 `workbench.initialize_review(db)` 分别建立站库和隔离库。初始化可以重复运行，保留已有数据。公开写入口负责自己的 SQLite 事务，调用时应使用没有待提交事务的连接。关闭连接后仍能用原路径和原号领取。每个入口的 `db` 为所属工作库连接。

| 阶段 | 入口 | 入参与返回 |
| --- | --- | --- |
| 核定量程 | `profiles.catalog.configure(db, batch, station, channels, coefficients, offset_bounds)` | 目录为两个或三个不同的物理通道名，系数字典按名完整覆盖目录，零偏为有序的一对界。返回 `ProfileReference`。配置更正再次调用以登记新版本。`read_configuration(db, reference)` 按原引用领取。 |
| 导入显示 | `capture.imports.ingest(db, reference, rows, parent_freeze_id=None)` | `rows` 为 `(通道名, 整数显示)` 序列，次序任意，要求完整且没有重复。返回 `DisplayRevision`。勘误填原冻结号，使用本次显式配置及完整更正行。 |
| 冻结与领取 | `capture.freezing.freeze(db, revision_id)` 与 `load_frozen_source(db, freeze_id)` | 返回 `FrozenSource`，其中含固定冻结号、原显示修订和确切量程版本。重复冻结同一修订得到同一冻结号。 |
| 发行 | `issue.register.issue_piece(db, freeze_id)` | 返回 `(StationPiece, IssueEntry)`。`read_issue_entry(db, issue_id)` 从本站登记领取可信交接副本。对同一冻结源重复发行时正文与摘要相同，每次发行有自己的发行号。 |
| 实收 | `receive.intake.receive_piece(db, piece, entry)` | 将完整来件与独立取得的可信发行登记相核对，返回整数实收号。`receive.holdings.ReceiptStore(db).read_receipt(receipt_id)` 领取已核快照。合法重投返回原号。 |
| 签报 | `reports.publish.compare(db, request)` | `reports.requests.ComparisonRequest(left_receipt_id, right_receipt_id, minuend, subtrahend)` 选择同批同目录的两站实收号和两个不同的通道。返回 `PublishedComparison`，含定稿、实际双件出处和回执。 |
| 历史领取 | `reports.history.read_report(db, report_id)` | 从隔离库领取原请求、原结论、原双件出处及原回执。 |

批次、台架和通道使用非空可打印名称，名称两端无空白，大小写有别。配置的有理数参数可用 `int`、`fractions.Fraction` 或有理数字符串，显示行仅接受整数，布尔值不是显示或刻度。未知号抛出 `KeyError`，输入或交接不合法抛出 `ValueError`，SQLite 写入错误按原异常返回。完整显示和相应索引在一次事务中登记。报告和成功回执同库提交，任一写入失败都回滚；旧成果仍可领取。

## 核算口径

实际读值和差值使用批次统一物理单位。换算系数为每物理单位的刻度数，零偏以刻度计。台架用 `a × x + b` 取最近整数，半刻度取偶数。偶数显示允许两侧半刻度，奇数显示排除两侧半刻度。同站同次所有通道共享一个 `b`，其允许区间在配置中是闭区间，两站各自选择本站零偏。发行件保全全部且仅有的具名可行读值，台架原始显示和零偏记录留站。发行登记绑定 V1 外层和正文字节的 SHA-256 摘要。登记应由白班另行可信交接，摘要用于核对正文完整性。

两站必须支持同一组实际读值，未请求的第三通道也参与可行性判断。相容定稿的 `result.status` 为 `compatible`，`result.difference` 给出 `lower`、`upper` 两个 `Fraction` 和 `lower_closed`、`upper_closed`。请求方向始终是前一通道减后一通道。单值是上下界相等的闭区间。`incompatible` 表示证据不相容，`difference` 为 `None`，照常签存双件出处和回执。持久化使用规范有理数字符串。计算和正文随输入确定，发行等业务编号是供追溯使用的独立标识。

## 正常样例

白班用相同单位刻度、零偏 0 导入甲站 `(0,0)` 和乙站 `(1,0)`。实际 `X=1/2` 只能显示 0，夜班签不相容。乙站勘误为 `(0,0)` 后，新报告的 `X−Y` 为 `[-1,1]`。晨班凭旧号仍能领取不相容定稿及原乙站件，凭新号领取改后的结论。回归还覆盖共享零偏、三个具名通道、开区间、闭单值、错件拒绝、回执拒写回滚、勘误父链和重复初始化。
