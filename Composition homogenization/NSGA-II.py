import pandas as pd
import numpy as np
import random
import matplotlib.pyplot as plt
import datetime

# --- 配置参数 ---

# VIP值
VIP_GANCAOGAN = 1.01558
VIP_GANCAOSUAN = 1.05139

# 计算权重
TOTAL_VIP = VIP_GANCAOGAN + VIP_GANCAOSUAN
WEIGHT_GANCAOGAN = VIP_GANCAOGAN / TOTAL_VIP
WEIGHT_GANCAOSUAN = VIP_GANCAOSUAN / TOTAL_VIP

# 要优化的成分列名
INGREDIENT_COLUMNS = ['甘草苷质量分数', '甘草酸质量分数']
SIMILARITY_COLUMN = '相似度'
CONTENT_WEIGHTS = np.array([WEIGHT_GANCAOGAN, WEIGHT_GANCAOSUAN])

# NSGA-II 算法参数
POPULATION_SIZE = 150
NUM_GENERATIONS = 400
CROSSOVER_PROB = 0.7
MUTATION_PROB = 0.3
MUTATION_STRENGTH = 0.1
NUM_BATCHES_TO_SELECT = 20

# --- 新增功能：移除极端解 ---
# True: 移除帕累托前沿两端的极端解
# False: 保留所有最优解
REMOVE_EXTREMES = False


# --- 目标函数 ---
def evaluate(raw_proportions, df, ingredient_columns, similarity_column, target_ingredients):
    final_proportions = np.zeros_like(raw_proportions)
    top_k_indices = np.argsort(raw_proportions)[-NUM_BATCHES_TO_SELECT:]
    final_proportions[top_k_indices] = raw_proportions[top_k_indices]

    sum_props = np.sum(final_proportions)
    if sum_props > 0:
        final_proportions /= sum_props
    else:
        return np.array([1e6, 1e6])

    blended_ingredients = np.dot(final_proportions, df[ingredient_columns].values)

    MIN_GANCAOGAN = 0.45
    MIN_GANCAOSUAN = 1.8
    if blended_ingredients[0] < MIN_GANCAOGAN or blended_ingredients[1] < MIN_GANCAOSUAN:
        return np.array([1e6, 1e6])

    weighted_deviation = np.sqrt(np.sum(CONTENT_WEIGHTS * ((blended_ingredients - target_ingredients) ** 2)))
    blended_similarity = np.dot(final_proportions, df[similarity_column].values)

    return np.array([weighted_deviation, -blended_similarity])


# ========== 核心算法函数（保持不变） ==========
def fast_non_dominated_sort(values):
    population_size = len(values)
    fronts = []
    S = [[] for _ in range(population_size)]
    n = [0] * population_size
    for p in range(population_size):
        for q in range(population_size):
            if p == q: continue
            if all(values[p] <= values[q]) and any(values[p] < values[q]):
                S[p].append(q)
            elif all(values[q] <= values[p]) and any(values[q] < values[p]):
                n[p] += 1
    front_0 = [p for p in range(population_size) if n[p] == 0]
    fronts.append(front_0)
    i = 0
    while i < len(fronts):
        next_front = []
        for p in fronts[i]:
            for q in S[p]:
                n[q] -= 1
                if n[q] == 0:
                    next_front.append(q)
        if next_front:
            fronts.append(next_front)
        i += 1
    return fronts


def crowding_distance(values, front):
    if not front: return {}
    num_objectives = values.shape[1]
    num_individuals = len(front)
    distances = {i: 0 for i in front}
    for m in range(num_objectives):
        sorted_front = sorted(front, key=lambda i: values[i, m])
        distances[sorted_front[0]] = float('inf')
        distances[sorted_front[-1]] = float('inf')
        if num_individuals > 2:
            min_val = values[sorted_front[0], m]
            max_val = values[sorted_front[-1], m]
            range_val = max_val - min_val
            if range_val == 0: continue
            for i in range(1, num_individuals - 1):
                distances[sorted_front[i]] += (values[sorted_front[i + 1], m] - values[
                    sorted_front[i - 1], m]) / range_val
    return distances


def selection(population, values, population_size):
    fronts = fast_non_dominated_sort(values)
    distances = {}
    for front in fronts:
        distances.update(crowding_distance(values, front))
    new_population_indices = []
    front_idx = 0
    while front_idx < len(fronts) and len(new_population_indices) + len(fronts[front_idx]) <= population_size:
        new_population_indices.extend(fronts[front_idx])
        front_idx += 1
    if len(new_population_indices) < population_size:
        if front_idx < len(fronts):
            last_front = fronts[front_idx]
            sorted_last_front = sorted(last_front, key=lambda i: distances[i], reverse=True)
            remaining_count = population_size - len(new_population_indices)
            new_population_indices.extend(sorted_last_front[:remaining_count])
    new_population = [population[i] for i in new_population_indices]
    return new_population


def crossover(parent1, parent2):
    child1, child2 = parent1.copy(), parent2.copy()
    if random.random() < CROSSOVER_PROB:
        alpha = random.random()
        child1 = alpha * parent1 + (1 - alpha) * parent2
        child2 = (1 - alpha) * parent1 + alpha * parent2
    return child1, child2


def mutate(individual):
    mutated_individual = individual.copy()
    for i in range(len(mutated_individual)):
        if random.random() < MUTATION_PROB:
            mutated_individual[i] += np.random.normal(0, MUTATION_STRENGTH)
            mutated_individual[i] = max(0, mutated_individual[i])
    return mutated_individual


# ========== 绘图和结果记录 ==========
def plot_pareto_fronts_english(kept_values, front2_values, timestamp):
    """
    绘制美化后的帕累托前沿对比图 (全英文，并显示移除的极端解)
    """
    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['font.serif'] = ['Times New Roman']
    plt.rcParams['axes.unicode_minus'] = False

    color_kept = '#005A9C'  # 专业蓝 (保留的解)
    color_front2 = '#F57F17'  # 亮橙色 (第二前沿)
    # color_removed = '#808080'  # 灰色 (移除的解)

    plt.figure(figsize=(14, 8))

    # 绘制保留的折衷解
    plt.scatter(kept_values[:, 0], -kept_values[:, 1],
                c=color_kept,
                marker='o',
                s=80,
                label='Front 1 (Compromise Solutions)',
                alpha=0.85,
                edgecolors='w',
                linewidth=0.5)

    # 绘制第二前沿
    if front2_values is not None and len(front2_values) > 0:
        plt.scatter(front2_values[:, 0], -front2_values[:, 1],
                    c=color_front2,
                    marker='X',
                    s=70,
                    label='Front 2',
                    alpha=0.8)

    # --- 新增：绘制被移除的极端解 ---
    # if removed_values is not None and len(removed_values) > 0:
    #     plt.scatter(removed_values[:, 0], -removed_values[:, 1],
    #                 c=color_removed,
    #                 marker='x',
    #                 s=100,
    #                 label='Front 1 (Extreme Solutions - Removed)',
    #                 linewidth=2)

    fontsize_title = 20
    fontsize_label = 18
    fontsize_legend = 16
    fontsize_ticks = 16

    plt.title("Final Pareto Front Comparison", fontsize=fontsize_title, fontweight='bold', pad=20)
    plt.xlabel("Objective 1: Weighted Content Deviation", fontsize=fontsize_label)
    plt.ylabel("Objective 2: Similarity", fontsize=fontsize_label)

    plt.legend(fontsize=fontsize_legend, loc='best', frameon=True, shadow=True)

    plt.xticks(fontsize=fontsize_ticks)
    plt.yticks(fontsize=fontsize_ticks)

    plt.grid(True, linestyle='--', alpha=0.6)

    english_title = "Final_Pareto_Front_Comparison"
    plt.savefig(f'{english_title}_{timestamp}.png', dpi=300, bbox_inches='tight')
    print(f"英文版帕累托前沿对比图已保存至: {english_title}_{timestamp}.png")


def evaluate_and_record(raw_prop, df, ingredient_columns, similarity_column, target_ingredients, plan_id):
    prop = np.zeros_like(raw_prop)
    top_k_indices = np.argsort(raw_prop)[-NUM_BATCHES_TO_SELECT:]
    prop[top_k_indices] = raw_prop[top_k_indices]
    prop /= np.sum(prop)
    obj = evaluate(prop, df, ingredient_columns, similarity_column, target_ingredients)
    blended_ingredients = np.dot(prop, df[ingredient_columns].values)
    used_batches_indices = np.where(prop > 0)[0]
    used_batches_proportions = prop[used_batches_indices]
    used_batches_ids = df['批次'].iloc[used_batches_indices].values
    batch_details = "; ".join(
        [f"{batch_id}: {proportion:.4f}" for batch_id, proportion in zip(used_batches_ids, used_batches_proportions)])
    return {
        '方案ID': plan_id,
        '目标1_含量偏离度': obj[0],
        '目标2_相似度': -obj[1],
        **{f'产出_{col}': val for col, val in zip(ingredient_columns, blended_ingredients)},
        '使用的批次数': np.sum(prop > 0),
        '批次使用详情': batch_details
    }


# ========== 主函数 ==========
if __name__ == "__main__":
    excel_file_name = "甘草_扩充样本500条0806v4.xlsx"
    try:
        df = pd.read_excel(excel_file_name)
    except FileNotFoundError:
        print(f"错误：找不到Excel文件 '{excel_file_name}'。")
        exit()
    except ImportError:
        print("错误：需要 'openpyxl' 库来读取 .xlsx 文件。请使用 'pip install openpyxl' 安装。")
        exit()

    TARGET_INGREDIENTS = df[INGREDIENT_COLUMNS].mean().values
    print(f"目标含量未指定，已自动使用数据平均值作为目标：")
    for i, col in enumerate(INGREDIENT_COLUMNS):
        print(f"  - {col}: {TARGET_INGREDIENTS[i]:.4f}")

    num_individuals = len(df)
    population = [np.random.dirichlet(np.ones(num_individuals), size=1).flatten() for _ in range(POPULATION_SIZE)]

    for gen in range(NUM_GENERATIONS):
        if (gen + 1) % 50 == 0 or gen == 0 or (gen + 1) == NUM_GENERATIONS:
            print(f"第 {gen + 1}/{NUM_GENERATIONS} 代...")

        offspring = []
        while len(offspring) < POPULATION_SIZE:
            p1, p2 = random.sample(population, 2)
            c1, c2 = crossover(p1, p2)
            offspring.append(mutate(c1))
            if len(offspring) < POPULATION_SIZE:
                offspring.append(mutate(c2))

        combined_population = population + offspring
        combined_obj_values = np.array(
            [evaluate(ind, df, INGREDIENT_COLUMNS, SIMILARITY_COLUMN, TARGET_INGREDIENTS) for ind in
             combined_population])
        population = selection(combined_population, combined_obj_values, POPULATION_SIZE)

    print("优化完成，正在生成最终结果...")

    final_objective_values = np.array(
        [evaluate(ind, df, INGREDIENT_COLUMNS, SIMILARITY_COLUMN, TARGET_INGREDIENTS) for ind in population])
    final_fronts = fast_non_dominated_sort(final_objective_values)

    # --- 结果处理：分离极端解和折衷解 ---

    # 原始的第一前沿
    pareto_front_indices_0 = final_fronts[0]

    kept_indices = list(pareto_front_indices_0)
    removed_indices = []

    if REMOVE_EXTREMES and len(pareto_front_indices_0) > 5:
        print(f"\n正在移除极端解...")
        # 提取第一前沿的目标值
        front_values = final_objective_values[pareto_front_indices_0]

        # 找到两个极端点的索引（在 front_values 内部的索引）
        # 极端点1: 含量偏差最小
        idx_min_dev = np.argmin(front_values[:, 0])
        # 极端点2: 相似度最高 (即-similarity最小)
        idx_max_sim = np.argmin(front_values[:, 1])

        # 获取这两个点在原始种群中的真实索引
        extreme_idx_1 = pareto_front_indices_0[idx_min_dev]
        extreme_idx_2 = pareto_front_indices_0[idx_max_sim]

        # 从保留列表中移除
        removed_indices = list({extreme_idx_1, extreme_idx_2})
        kept_indices = [idx for idx in pareto_front_indices_0 if idx not in removed_indices]

        print(f"已识别并移除 {len(removed_indices)} 个极端解。剩余 {len(kept_indices)} 个折中解。")
    else:
        print("\n未移除极端解（少于5个最优解或功能已关闭）。")

    # 根据处理后的索引列表，获取相应的数据
    kept_solutions = [population[i] for i in kept_indices]
    kept_values = final_objective_values[kept_indices]
    removed_values = final_objective_values[removed_indices]

    # 获取第二前沿的数据
    pareto_values_1 = None
    if len(final_fronts) > 1:
        pareto_front_indices_1 = final_fronts[1]
        pareto_values_1 = final_objective_values[pareto_front_indices_1]

    # --- 绘图和保存 ---
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    plot_pareto_fronts_english(kept_values, pareto_values_1, timestamp)

    # 将保留的折衷解保存到CSV
    results = []
    for i, sol in enumerate(kept_solutions):
        plan_id = f"方案_{i + 1}"
        results.append(evaluate_and_record(sol, df, INGREDIENT_COLUMNS, SIMILARITY_COLUMN, TARGET_INGREDIENTS, plan_id))

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        cols_to_move = ['方案ID', '目标1_含量偏离度', '目标2_相似度', '使用的批次数', '批次使用详情']
        new_order = cols_to_move + [col for col in results_df.columns if col not in cols_to_move]
        results_df = results_df[new_order]
        results_df = results_df.sort_values(by='目标1_含量偏离度', ascending=True)

    output_filename = f'pareto_solutions_{timestamp}.csv'
    results_df.to_csv(output_filename, index=False, encoding='utf-8-sig')

    print(f"最优折衷配比方案已保存至 '{output_filename}'")