import pandas as pd
import numpy as np
import random
import matplotlib.pyplot as plt


def run_final_optimization_with_constraints():
    """
    主函数：加载Excel数据并执行NSGA-II优化，最终结果图增强层次可视化。
    """
    # --- 步骤1：加载您的 .xlsx 文件 ---
    file_path = '甘草扩充样本500条0801v3.xlsx'
    try:
        df = pd.read_excel(file_path)
        print(f"成功加载Excel文件 '{file_path}'，共 {len(df)} 条批次数据。")
    except FileNotFoundError:
        print(f"错误：找不到文件 '{file_path}'。")
        return
    except Exception as e:
        print(f"读取Excel文件时发生错误: {e}。")
        return

    # --- 步骤2：定义列名、目标、权重和约束 ---
    ingredient_columns = ['甘草苷百分含量', '甘草酸百分含量']
    similarity_column = '相似度'

    target_ingredients = df[ingredient_columns].mean().values
    NUM_BATCHES = len(df)
    content_weights = np.array([0.3, 0.7])
    MIN_LIQUIRITIN_CONTENT = 0.45
    MIN_GLYCYRRHIZIN_CONTENT = 1.8

    print("\n已设定最终的优化目标及约束...")

    # --- 步骤3：定义目标函数 ---
    def evaluate(proportions):
        blended_ingredients = np.dot(proportions, df[ingredient_columns].values)
        if blended_ingredients[0] < MIN_LIQUIRITIN_CONTENT or blended_ingredients[1] < MIN_GLYCYRRHIZIN_CONTENT:
            return np.array([1e6, 1e6])
        weighted_deviation = np.sqrt(np.sum(content_weights * ((blended_ingredients - target_ingredients) ** 2)))
        blended_similarity = np.dot(proportions, df[similarity_column].values)
        return np.array([weighted_deviation, -blended_similarity])

    # --- 步骤4：NSGA-II 核心函数 ---
    def fast_non_dominated_sort(objectives):
        pop_size = len(objectives)
        S, n = [[] for _ in range(pop_size)], [0] * pop_size
        fronts = [[]]
        for p in range(pop_size):
            for q in range(pop_size):
                if np.all(objectives[p] <= objectives[q]) and np.any(objectives[p] < objectives[q]):
                    S[p].append(q)
                elif np.all(objectives[q] <= objectives[p]) and np.any(objectives[q] < objectives[p]):
                    n[p] += 1
            if n[p] == 0: fronts[0].append(p)
        i = 0
        while i < len(fronts) and fronts[i]:
            next_front = []
            for p in fronts[i]:
                for q in S[p]:
                    n[q] -= 1
                    if n[q] == 0: next_front.append(q)
            i += 1
            if next_front: fronts.append(next_front)
        return fronts

    def calculate_crowding_distance(indices, objectives):
        distances = {i: 0 for i in indices}
        if not indices: return distances
        for m in range(len(objectives[0])):
            sorted_indices = sorted(indices, key=lambda i: objectives[i][m])
            distances[sorted_indices[0]] = distances[sorted_indices[-1]] = float('inf')
            obj_range = objectives[sorted_indices[-1]][m] - objectives[sorted_indices[0]][m]
            if obj_range == 0: continue
            for i in range(1, len(sorted_indices) - 1):
                distances[sorted_indices[i]] += (objectives[sorted_indices[i + 1]][m] -
                                                 objectives[sorted_indices[i - 1]][m]) / obj_range
        return distances

    def selection(population, ranks, distances):
        idx1, idx2 = random.sample(range(len(population)), 2)
        r1, r2, d1, d2 = ranks.get(idx1), ranks.get(idx2), distances.get(idx1), distances.get(idx2)
        if r1 < r2: return population[idx1]
        if r2 < r1: return population[idx2]
        if d1 > d2: return population[idx1]
        return population[idx2]

    # --- 步骤5：进化主流程 ---
    pop_size = 100
    num_generations = 300

    population = [p / np.sum(p) for p in np.random.rand(pop_size, NUM_BATCHES)]

    print("\n开始最终的进化计算...")
    for gen in range(num_generations):
        objectives = np.array([evaluate(ind) for ind in population])
        fronts = fast_non_dominated_sort(objectives)
        ranks = {idx: i for i, front in enumerate(fronts) for idx in front}
        distances = {idx: dist for front in fronts for idx, dist in
                     calculate_crowding_distance(front, objectives).items()}

        offspring = []
        while len(offspring) < pop_size:
            p1 = selection(population, ranks, distances)
            p2 = selection(population, ranks, distances)
            c1 = 0.5 * p1 + 0.5 * p2
            if random.random() < 0.1:
                c1 += np.random.normal(0, 0.02, size=len(c1))
                c1[c1 < 0] = 0
            if np.sum(c1) > 0: offspring.append(c1 / np.sum(c1))

        combined_pop = population + offspring
        combined_obj = np.array([evaluate(ind) for ind in combined_pop])
        new_fronts = fast_non_dominated_sort(combined_obj)

        new_population = []
        for front in new_fronts:
            if len(new_population) + len(front) <= pop_size:
                new_population.extend([combined_pop[i] for i in front])
            else:
                dist = calculate_crowding_distance(front, combined_obj)
                sorted_front = sorted(front, key=lambda i: dist[i], reverse=True)
                new_population.extend([combined_pop[i] for i in sorted_front[:pop_size - len(new_population)]])
                break
        population = new_population

        if (gen + 1) % 50 == 0:
            print(f"  第 {gen + 1}/{num_generations} 代完成...")

    # --- 步骤6：结果处理与增强可视化 ---
    print("\n计算完成！正在分析最终种群...")

    # **新的分析方法：对最终种群的所有个体进行评估和分层**
    final_objectives = np.array([evaluate(ind) for ind in population])
    final_fronts = fast_non_dominated_sort(final_objectives)

    # 准备绘图数据
    plot_data = {'f1': [], 'f2': []}

    # 遍历第一前沿
    for idx in final_fronts[0]:
        # 检查该解是否满足约束条件
        if final_objectives[idx][0] < 1e5:  # 检查惩罚值
            plot_data['f1'].append(final_objectives[idx])

    # 遍历第二前沿 (如果存在)
    if len(final_fronts) > 1:
        for idx in final_fronts[1]:
            if final_objectives[idx][0] < 1e5:
                plot_data['f2'].append(final_objectives[idx])

    plot_data['f1'] = np.array(plot_data['f1'])
    plot_data['f2'] = np.array(plot_data['f2'])

    # 转回正的相似度以便于理解
    if len(plot_data['f1']) > 0:
        plot_data['f1'][:, 1] *= -1
    if len(plot_data['f2']) > 0:
        plot_data['f2'][:, 1] *= -1

    print(f"在所有合格解中，找到 {len(plot_data['f1'])} 个最优解 (第一前沿)。")
    if len(plot_data['f2']) > 0:
        print(f"同时找到 {len(plot_data['f2'])} 个次优解 (第二前沿)。")
    else:
        print("未在最终种群中找到属于第二前沿的合格解。")

    # **美化绘图**
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.figure(figsize=(14, 9))
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False

    # 绘制第一前沿
    if len(plot_data['f1']) > 0:
        plt.scatter(plot_data['f1'][:, 0], plot_data['f1'][:, 1], c='red', marker='o', s=60,
                    label='Pareto Front (Rank 1 / 最优解)', alpha=0.8, zorder=3)

    # 绘制第二前沿
    if len(plot_data['f2']) > 0:
        plt.scatter(plot_data['f2'][:, 0], plot_data['f2'][:, 1], c='blue', marker='^', s=35,
                    label='Second Front (Rank 2 / 次优解)', alpha=0.6, zorder=2)

    plt.title('甘草混批优化：第一与第二Pareto前沿对比', fontsize=18)
    plt.xlabel('目标1: 加权成分含量偏离度 (值越小越好)', fontsize=12)
    plt.ylabel('目标2: 指纹图谱相似度 (值越大越好)', fontsize=12)
    plt.legend(fontsize=12)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)

    plt.savefig('pareto_front_comparison_v2.png')
    print("\n最终结果对比图已保存为 'pareto_front_comparison_v2.png'")


if __name__ == "__main__":
    run_final_optimization_with_constraints()