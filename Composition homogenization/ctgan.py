from ctgan import CTGAN
import pandas as pd

# 读取原始 Excel 中“甘草”sheet的数据（注意 header=1 是从第二行开始）
df = pd.read_excel("中药数据.xlsx", sheet_name="甘草", header=1)

# 提取数值字段（根据表头实际情况调整）
columns = ['相似度', '芦糖甘草苷质量分数', '甘草苷质量分数', '异甘草苷质量分数', '甘草素质量分数', '异甘草素质量分数', '甘草酸质量分数', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11']
df = df[columns].apply(pd.to_numeric, errors='coerce').dropna()

# 初始化 CTGAN 合成器，设置训练轮数
ctgan = CTGAN(epochs=300)
ctgan.fit(df, discrete_columns=[])

# 假设原始数据有 ~40 条，生成 460 条补足到 500
new_data = ctgan.sample(460)

# 合并原始 + 生成数据
df_all = pd.concat([df, new_data], ignore_index=True)
df_all.to_excel("甘草_扩充样本500条0806v4.xlsx", index=False)

print("✅ 甘草数据扩充完成，已保存为 甘草_扩充样本500条0806v4.xlsx")
