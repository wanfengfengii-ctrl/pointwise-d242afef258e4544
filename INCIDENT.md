# 夜班差值误签

白班按 `samples/day.json` 导入甲、乙第 17 批显示，两个通道均为单位刻度，两站零偏均为 0。甲站 X、Y 分别显示 0、0，乙站显示 1、0。夜班实收两份冻结件，关闭两站库，按 `samples/night.json` 请求 X−Y。

现有定稿给出 `compatible` 和闭区间 `[0,1]`。两个 X 读值范围的闭包只在 1/2 处相接，1/2 取最近偶数为 0，乙站的 X 显示 1 排除了这个值。正确的定稿为 `incompatible`，`difference` 为 `None`，照常保存两份实收出处和回执。

白班按 `samples/morning.json` 将乙站勘误为 0、0 并另发站件后，用新实收号核定应得闭区间 `[-1,1]`。重开隔离库后，原号仍应领取不相容定稿及原出处和回执，新号对应改后的结论。

```sh
python3 -B -m unittest -v tests.test_comparison.TestComparison.test_half_tick_contact
```

完整核验和工作日演示沿用 README.md 中的入口。
