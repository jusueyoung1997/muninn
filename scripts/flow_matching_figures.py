"""Rebuild the article's figures: uv run --with numpy --with matplotlib scripts/flow_matching_figures.py."""

from pathlib import Path
from html import escape
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public/images/flow-matching"
OUT.mkdir(parents=True, exist_ok=True)
for candidate in [
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]:
    if Path(candidate).exists():
        font_manager.fontManager.addfont(candidate)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=candidate).get_name()
        break
plt.rcParams.update({
    "svg.fonttype": "path",
    "svg.hashsalt": "muninn-flow-matching",
    "axes.unicode_minus": False,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#bfc6bc",
    "axes.labelcolor": "#626b60",
    "xtick.color": "#798174",
    "ytick.color": "#798174",
    "text.color": "#30382f",
    "font.size": 11,
    "figure.facecolor": "#f9f8f5",
    "axes.facecolor": "#f9f8f5",
})
MEANS = np.array([[-2.0, 0.8], [2.0, -0.8]])
SIGMA = 0.4


def velocity(x, t):
    """E[X1-X0 | Xt=x] for independent endpoints and a two-Gaussian target."""
    s2 = (1 - t) ** 2 + t ** 2 * SIGMA ** 2
    b = t * SIGMA ** 2 - (1 - t)
    centered = x[..., None, :] - t * MEANS
    logits = -(centered ** 2).sum(axis=-1) / (2 * s2)
    weights = np.exp(logits - logits.max(axis=-1, keepdims=True))
    weights /= weights.sum(axis=-1, keepdims=True)
    conditional = MEANS + b / s2 * centered
    return (weights[..., None] * conditional).sum(axis=-2)


def density(x, t):
    s2 = (1 - t) ** 2 + t ** 2 * SIGMA ** 2
    centered = x[..., None, :] - t * MEANS
    return np.exp(-(centered ** 2).sum(axis=-1) / (2 * s2)).mean(axis=-1) / (2 * np.pi * s2)


def solve(x0, steps=400):
    """Fixed-step classical RK4; the analytic field is defined on [0,1]."""
    h = 1 / steps
    x = x0.copy()
    history = [x.copy()]
    for k in range(steps):
        t = k * h
        k1 = velocity(x, t)
        k2 = velocity(x + h * k1 / 2, t + h / 2)
        k3 = velocity(x + h * k2 / 2, t + h / 2)
        k4 = velocity(x + h * k3, t + h)
        x += h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
        history.append(x.copy())
    return np.stack(history)


def validate():
    # Check the continuity equation independently by centered finite differences.
    x = np.array([[-1.1, 0.3], [0.4, 1.0], [1.5, -0.7], [-0.2, -0.3]])
    h = 1e-5
    residual = []
    for t in [0.2, 0.5, 0.8]:
        dt = (density(x, t + h) - density(x, t - h)) / (2 * h)
        divergence = np.zeros(len(x))
        for j in range(2):
            delta = np.zeros_like(x)
            delta[:, j] = h
            plus = density(x + delta, t) * velocity(x + delta, t)[:, j]
            minus = density(x - delta, t) * velocity(x - delta, t)[:, j]
            divergence += (plus - minus) / (2 * h)
        residual.extend(np.abs(dt + divergence))
    assert max(residual) < 1e-7, max(residual)
    probe = np.random.default_rng(91).normal(size=(16, 2))
    coarse, fine = solve(probe, 200), solve(probe, 400)
    difference = np.max(np.abs(coarse - fine[::2]))
    assert difference < 1e-7, difference
    print(f"Continuity residual: {max(residual):.2e}; RK4 step-doubling difference: {difference:.2e}")


grid_x, grid_y = np.meshgrid(np.linspace(-3.6, 3.6, 170), np.linspace(-2.8, 2.8, 145))
GRID = np.stack([grid_x, grid_y], axis=-1)


def style_axis(ax):
    ax.set(xlim=(-3.6, 3.6), ylim=(-2.8, 2.8), aspect="equal")
    ax.set_xticks([-3, 0, 3])
    ax.set_yticks([-2, 0, 2])
    ax.tick_params(labelsize=9, length=3)


def paths_figure():
    rng = np.random.default_rng(20261104)
    x0 = rng.normal(size=(9, 2))
    x1 = MEANS[rng.integers(0, 2, size=len(x0))] + SIGMA * rng.normal(size=x0.shape)
    ode = solve(x0)
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.25), dpi=100)
    fig.subplots_adjust(left=0.065, right=0.975, top=0.80, bottom=0.15, wspace=0.19)
    fig.text(0.065, 0.94, "同一批噪声起点，两种不同的运动", fontsize=21)
    fig.text(0.065, 0.885, "参考路径保留端点配对；ODE 轨迹不断查询当前位置的条件平均速度。", fontsize=12, color="#697263")
    colors = ["#557a6a", "#9b7750", "#6683a0", "#a26b78", "#8b8651", "#8a75a2", "#6e9291", "#a8775d", "#65714b"]
    for ax, title in zip(axes, ["端点插值：每条都是直线", "生成 ODE：轨迹可以弯曲"]):
        style_axis(ax)
        for t, color in [(0, "#d0d2c9"), (1, "#b6c2b0")]:
            pdf = density(GRID, t)
            ax.contour(grid_x, grid_y, pdf, levels=pdf.max() * np.array([0.13, 0.45]),
                       colors=color, linewidths=0.8)
        ax.set_title(title, fontsize=15, pad=20)
        ax.set_xlabel("第一维")
    axes[0].set_ylabel("第二维")
    for i, color in enumerate(colors):
        line = np.linspace(0, 1, 101)[:, None] * (x1[i] - x0[i]) + x0[i]
        for ax, path in zip(axes, [line, ode[:, i]]):
            ax.plot(path[:, 0], path[:, 1], color=color, lw=1.8, alpha=0.92)
            ax.scatter(*path[0], s=37, color=color, edgecolors="#f9f8f5", linewidths=0.8, zorder=4)
            ax.scatter(*path[-1], marker="x", s=44, color=color, linewidths=1.5, zorder=4)
            j = int(len(path) * 0.55)
            ax.annotate("", xy=path[j + 3], xytext=path[j - 3],
                        arrowprops={"arrowstyle": "->", "color": color, "lw": 1.3})
    fig.text(0.065, 0.055, "● 噪声起点    × 各自的终点    淡灰 / 淡绿：起点与数据分布的等高线", fontsize=11, color="#697263")
    fig.savefig(OUT / "paths.svg", metadata={"Date": None})
    plt.close(fig)


def marginals_figure():
    rng = np.random.default_rng(170)
    count = 800
    x0 = rng.normal(size=(count, 2))
    x1 = MEANS[rng.integers(0, 2, size=count)] + SIGMA * rng.normal(size=(count, 2))
    ode = solve(x0)
    fig, axes = plt.subplots(2, 5, figsize=(12, 6.5), dpi=100)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.80, bottom=0.12, hspace=0.20, wspace=0.12)
    fig.text(0.075, 0.945, "轨迹不同，各时刻的边缘分布相同", fontsize=21)
    fig.text(0.075, 0.89, "同一二维双峰例子；每幅显示 800 个样本，背景为该时刻的解析密度。", fontsize=12, color="#697263")
    for j, t in enumerate([0, 0.25, 0.5, 0.75, 1]):
        reference = (1 - t) * x0 + t * x1
        generated = ode[int(round(t * 400))]
        pdf = density(GRID, t)
        for row, (points, color) in enumerate([(reference, "#6b8b79"), (generated, "#617d98")]):
            ax = axes[row, j]
            style_axis(ax)
            ax.contour(grid_x, grid_y, pdf, levels=pdf.max() * np.array([0.12, 0.4, 0.75]),
                       colors="#c4cabb", linewidths=0.65)
            ax.scatter(points[:, 0], points[:, 1], s=2.4, color=color, alpha=0.48,
                       edgecolors="none", rasterized=True)
            if row == 0:
                ax.set_title(f"t = {t:g}", fontsize=13, pad=12)
                ax.set_xticklabels([])
            if j:
                ax.set_yticklabels([])
        if j == 0:
            axes[0, j].set_ylabel("端点插值", fontsize=13, labelpad=15)
            axes[1, j].set_ylabel("生成 ODE", fontsize=13, labelpad=15)
    fig.text(0.075, 0.05, "观察整团概率质量的位置与形状；有限样本图不要求点对点重合。", fontsize=11, color="#697263")
    fig.savefig(OUT / "marginals.svg", metadata={"Date": None})
    plt.close(fig)


def pipeline_figure():
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620" role="img" aria-labelledby="title desc">',
        '<title id="title">Flow Matching 文生图：训练与推理</title>',
        '<desc id="desc">训练中从图片与噪声端点构造插值位置和速度标签；推理从新噪声出发，用文本条件和速度网络反复更新 latent，再解码。</desc>',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="none" stroke="#6d8373" stroke-width="1.4"/></marker></defs>',
        '<rect width="1200" height="620" rx="14" fill="#f9f8f5"/>',
        '<g font-family="system-ui,-apple-system,PingFang SC,Microsoft YaHei,sans-serif" fill="#30382f">',
        '<text x="38" y="43" font-size="24" font-weight="600">从训练标签，到文生图采样</text>',
    ]

    def text(x, y, value, size=15, muted=False):
        parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{"#6b7465" if muted else "#30382f"}">{escape(value)}</text>')

    def box(x, y, w, label, detail):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="77" rx="8" fill="#fffefa" stroke="#c9d0c2"/>')
        text(x + 15, y + 30, label, 18)
        text(x + 15, y + 56, detail, 13, True)

    def arrow(path):
        parts.append(f'<path d="{path}" fill="none" stroke="#6d8373" stroke-width="1.8" marker-end="url(#arrow)"/>')

    text(38, 91, "训练：由已知端点制造标签", 17)
    box(38, 120, 175, "图片 I → 编码器 E", "得到数据 latent z₁")
    box(38, 222, 175, "随机噪声 z₀", "与 z₁ 同形状")
    box(285, 173, 218, "线性插值 zₜ", "(1−t)z₀ + tz₁")
    box(594, 173, 206, "速度网络 vθ", "输入 zₜ、时间 t、文本 c")
    box(889, 173, 270, "速度 MSE", "预测速度 ↔ 端点差 z₁−z₀")
    box(520, 64, 280, "prompt → 文本编码器 T", "提供文本条件 c")
    arrow("M213 158H248V198H274")
    arrow("M213 260H248V225H274")
    arrow("M503 211H583")
    arrow("M800 211H878")
    arrow("M695 141V162")
    arrow("M125 299V326H1023V260")
    text(320, 316, "由这对端点直接计算速度标签 z₁−z₀", 14, True)
    parts.append('<path d="M38 352H1159" stroke="#dce0d5"/>')
    text(38, 389, "推理：固定文本条件，多次调用速度网络；此时没有目标图片", 17)
    box(38, 445, 175, "新噪声 ẑ₀", "采样起点")
    box(285, 445, 218, "ODE 求解器", "维护当前 latent 与时间")
    box(594, 445, 206, "速度网络 vθ", "使用固定文本条件 c")
    box(889, 445, 270, "解码器 D → 图片 Î", "求解结束后解码 ẑ₁")
    arrow("M213 483H274")
    arrow("M503 468H583")
    arrow("M594 501H514")
    arrow("M394 522V563H1023V533")
    text(536, 453, "查询", 13, True)
    text(531, 520, "返回速度", 13, True)
    text(495, 555, "到达 t=1，输出最终 latent", 14, True)
    parts.append("</g></svg>")
    (OUT / "text-to-image.svg").write_text("\n".join(parts))


if __name__ == "__main__":
    validate()
    paths_figure()
    marginals_figure()
    pipeline_figure()
    for svg in OUT.glob("*.svg"):
        svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    print("Wrote:", ", ".join(p.name for p in sorted(OUT.iterdir())))
