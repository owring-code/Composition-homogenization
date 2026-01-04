import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import shap
from lightgbm import LGBMRegressor
from sklearn.model_selection import train_test_split

# --- 1. 读取与预处理数据 ---
# 请将您的Excel文件与此脚本放在同一目录下
FILE_PATH = '甘草_扩充样本500条0728v2.xlsx'

try:
    df = pd.read_excel(FILE_PATH)
    print(f"成功读取文件: {FILE_PATH}，共 {df.shape[0]} 条数据。")
except FileNotFoundError:
    print(f"错误：未找到文件 '{FILE_PATH}'。请确保文件与代码在同一目录下。")
    exit()

# 数据清洗，确保所有列均为数值型
for col in df.columns:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# 首先删除包含任何空值的行
df.dropna(inplace=True)
print(f"删除空值行后，剩余 {df.shape[0]} 条数据。")

# 新增：删除任何一列中包含负值的行
# (df < 0) 会创建一个布尔值的DataFrame，.any(axis=1)会检查哪一行包含至少一个True
rows_with_negatives = (df < 0).any(axis=1)
df = df[~rows_with_negatives]
print(f"删除包含负值的行后，剩余有效数据 {df.shape[0]} 条。")
print("-" * 60)

df.reset_index(drop=True, inplace=True)

# --- 2. 实现您提供的详细评分函数 ---

# 首先，为需要统计分布的列计算均值和标准差
stats = {}
stat_cols_from_user = ['甘草素', '异甘草苷']
for col in stat_cols_from_user:
    if col in df.columns:
        stats[col] = {'mean': df[col].mean(), 'std': df[col].std()}
    else:
        stats[col] = {'mean': 0, 'std': 1e-9}
        print(f"警告: 在Excel中未找到列 '{col}'，将无法进行相关评分。")


def calculate_rubric_score(row):
    """根据用户提供的详细评分标准和确切列名为单行数据打分"""
    scores = {}

    # 核心功效成分评分
    ga = row.get('甘草酸1', 0)
    if ga >= 2.5:
        scores['甘草酸'] = 5
    elif ga >= 2.0:
        scores['甘草酸'] = 4
    elif ga >= 1.5:
        scores['甘草酸'] = 3
    else:
        scores['甘草酸'] = 1

    gg = row.get('甘草苷1', 0)
    if gg >= 0.6:
        scores['甘草苷'] = 5
    elif gg >= 0.5:
        scores['甘草苷'] = 4
    elif gg >= 0.4:
        scores['甘草苷'] = 3
    else:
        scores['甘草苷'] = 1

    igs = row.get('异甘草素', 0)
    if igs >= 0.06:
        scores['异甘草素'] = 5
    elif igs >= 0.05:
        scores['异甘草素'] = 4
    elif igs >= 0.04:
        scores['异甘草素'] = 3
    else:
        scores['异甘草素'] = 1

    # 其他特征成分（基于统计分布）
    def score_by_stats(value, col_name):
        if col_name not in stats: return 0
        mean, std = stats[col_name]['mean'], stats[col_name]['std']
        if value > mean + std:
            return 5
        elif value >= mean:
            return 4
        elif value >= mean - std:
            return 3
        else:
            return 1

    scores['甘草素'] = score_by_stats(row.get('甘草素', 0), '甘草素')
    scores['异甘草苷'] = score_by_stats(row.get('异甘草苷', 0), '异甘草苷')

    # 整体质量一致性评分
    sim = row.get('相似度', 0)
    if sim >= 0.99:
        scores['相似度'] = 5
    elif sim >= 0.98:
        scores['相似度'] = 4
    elif sim >= 0.97:
        scores['相似度'] = 3
    else:
        scores['相似度'] = 1

    weights = {
        '甘草酸': 0.35, '甘草苷': 0.25, '异甘草素': 0.10,
        '甘草素': 0.05, '异甘草苷': 0.05,
        '相似度': 0.15 + 0.05
    }

    total_score = sum(scores.get(key, 0) * weight for key, weight in weights.items())
    return total_score


# 应用评分函数生成“标准分”
df['Rubric_Score'] = df.apply(calculate_rubric_score, axis=1)
print("已根据您的评分细则，为所有批次计算了“标准分 (Rubric Score)”。")
print("-" * 60)

# --- 3. 训练机器学习模型 ---
features_for_model = [col for col in df.columns if col not in ['Rubric_Score']]
X = df[features_for_model]
y = df['Rubric_Score']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = LGBMRegressor(random_state=42, n_estimators=200, n_jobs=-1)
model.fit(X_train, y_train)
print("LightGBM 机器学习模型训练完成。")
score_r2 = model.score(X_test, y_test)
print(f"模型在测试集上的R²分数: {score_r2:.4f} (越接近1越好)")

# --- 4. 生成预测评分并进行SHAP分析 ---
df['ML_Score'] = model.predict(X)
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)
print("SHAP值计算完成。")
print("-" * 60)

# --- 5. 生成一系列漂亮的可视化图表 ---
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 图1: SHAP 蜂窝散点图
print("正在生成SHAP蜂窝图...")
plt.figure()
shap.summary_plot(shap_values, X_test, plot_type="beeswarm", max_display=15, show=False)
plt.title('SHAP 蜂窝图：特征对模型预测（质量评分）的影响', fontsize=16)
plt.xlabel('SHAP 值 (对模型输出的影响)')
plt.tight_layout()
plt.savefig("shap_beeswarm_plot_lgbm.png")
plt.show()

# 图2: 综合图表报告
fig, axes = plt.subplots(2, 2, figsize=(18, 14))
fig.suptitle('甘草批次质量机器学习分析报告 (LightGBM)', fontsize=20)

# 2a: 评分对比图
sns.regplot(x='Rubric_Score', y='ML_Score', data=df, ax=axes[0, 0],
            scatter_kws={'alpha': 0.6}, line_kws={'color': 'darkred', 'linestyle': '--'})
axes[0, 0].set_title('“标准分” vs “ML预测分” (模型学习效果)', fontsize=14)
axes[0, 0].set_xlabel('基于您规则计算的标准分', fontsize=12)
axes[0, 0].set_ylabel('机器学习预测的质量分', fontsize=12)
axes[0, 0].grid(True)

# 2b: ML评分分布
sns.histplot(df['ML_Score'], kde=True, ax=axes[0, 1], bins=30, color='darkcyan')
axes[0, 1].set_title('机器学习评分 (ML Score) 分布情况', fontsize=14)
axes[0, 1].set_xlabel('ML Score', fontsize=12)
axes[0, 1].set_ylabel('批次数', fontsize=12)

# 2c: 特征重要性
importances = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
importances.head(15).plot(kind='barh', ax=axes[1, 0], color='coral')
axes[1, 0].set_title('模型特征重要性 Top 15', fontsize=14)
axes[1, 0].invert_yaxis()
axes[1, 0].set_xlabel('重要性分数', fontsize=12)

# 2d: 关键特征与评分的热力图
corr_cols_for_heatmap = ['ML_Score', '甘草酸1', '甘草苷1', '相似度', '异甘草素']
corr_cols_exist = [col for col in corr_cols_for_heatmap if col in df.columns]
corr_matrix = df[corr_cols_exist].corr()
sns.heatmap(corr_matrix, annot=True, cmap='viridis', fmt='.2f', ax=axes[1, 1])
axes[1, 1].set_title('关键指标与ML评分的相关性热力图', fontsize=14)

plt.tight_layout(rect=[0, 0.03, 1, 0.95])
plt.savefig("comprehensive_analysis_report_lgbm.png")
plt.show()

# --- 6. 保存最终结果 ---
df_sorted = df.sort_values(by='ML_Score', ascending=False)
output_filename = '甘草批次_含LGBM评分_结果.xlsx'
df_sorted.to_excel(output_filename, index=False)

print(f"\n所有分析已完成！包含新版评分的最终结果已保存至: '{output_filename}'")
print("\n--------- 基于新规则和LGBM评分的 Top 10 批次 ---------")
display_cols_exist = [col for col in ['甘草酸1', '甘草苷1', '相似度', 'Rubric_Score', 'ML_Score'] if
                      col in df_sorted.columns]
print(df_sorted[display_cols_exist].head(10))
