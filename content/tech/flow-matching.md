---
title: "Flow Matching：从条件轨迹到生成速度场"
description: "从端点插值、条件期望到 ODE 采样，理解文生图模型如何学习生成。"
date: 2026-11-02
tags: [生成模型, Flow Matching]
draft: false
---

Flow Matching 最吸引人的地方，是它把一个看起来很难监督的问题，变成了一个能够直接构造标签的回归问题。

我们不知道怎样把任意一团噪声搬运成真实图片，但可以先从数据集中取一张图片，再随机取一份噪声，为这一对端点画一条直线。直线上的位置、时间和速度都能直接算出来。真正需要解释的是：**许多互不协调的直线，为什么能训练出一个统一的生成速度场？**

本文固定以下约定：

$$
X_0\sim p_0=\mathcal N(0,I),\qquad
X_1\sim p_1=p_{\mathrm{data}},\qquad t:0\longrightarrow 1.
$$

大写表示随机变量，小写表示具体取值；$X_t$ 表示训练中构造的参考运动，$Y_t$ 表示沿 ODE 移动的生成样本。两者在同一时刻可以具有相同的分布，但单条轨迹通常不同。全文先讨论无条件生成，第 7 节再加入文本。

## 1. 生成问题：怎样让噪声分布变成数据分布？

从一个噪声样本 $y_0$ 出发，给它规定当前位置与时间下的运动速度：

$$
\frac{dy_t}{dt}=v_\theta(y_t,t),\qquad y_{t=0}=y_0.
$$

这里 $v_\theta:\mathbb R^d\times[0,1]\to\mathbb R^d$ 是神经网络。同一个网络既接收位置，也接收时间，输出一个与位置同维度的速度向量。

微分方程也可以写成积分形式：

$$
y_t=y_0+\int_0^t v_\theta(y_s,s)\,ds.
$$

它描述的是：起点加上沿途累积的位移，得到当前位置。速度必须在不断变化的位置 $y_s$ 上计算，不能始终拿起点的预测代替。

如果初值也随机采样，$Y_0\sim p_0$，那么每个初值都对应一条轨迹，全部轨迹共同决定时刻 $t$ 的分布。设 ODE 的解映射为 $\Phi^\theta_{0,t}$，则生成分布为

$$
q_t=(\Phi^\theta_{0,t})_\#p_0.
$$

符号 $\# $ 表示推前：先按 $p_0$ 抽样，再把样本送进同一个映射，得到新的分布。生成目标是让

$$
q_1\approx p_{\mathrm{data}}.
$$

**一条轨迹回答“这个样本怎样走”；分布演化回答“所有样本的概率质量怎样移动”。** 我们最终关心后者，因为生成任务没有为每一份新噪声指定唯一的正确图片。

但训练数据只有图片。我们既没有现成的 $v_\theta$，也不知道哪个真实速度场能完成这次运输。监督标签从哪里来？

## 2. 构造路径：用一对端点制造中间状态与速度标签

先规定训练时怎样配对端点。本文采用独立配对：

$$
X_0\sim p_0,\qquad X_1\sim p_{\mathrm{data}},
\qquad X_0\perp X_1.
$$

每次随机取一份噪声和一个数据样本，不要求它们有语义对应关系。再定义线性插值：

$$
\boxed{X_t=(1-t)X_0+tX_1.}
$$

固定某一对具体端点 $(x_0,x_1)$，它的参考轨迹是

$$
x_t=(1-t)x_0+tx_1.
$$

对时间求导，直接得到这一对端点的速度：

$$
\frac{dx_t}{dt}=x_1-x_0.
$$

于是定义随机速度标签

$$
\boxed{U=X_1-X_0.}
$$

| 对象 | 含义 |
| --- | --- |
| $X_t$ | 随机端点插值得到的中间样本 |
| $p_t=\operatorname{Law}(X_t)$ | 时刻 $t$ 的边缘分布 |
| $U=X_1-X_0$ | 当前端点对提供的速度标签 |

“边缘”表示把端点的身份积分掉，只观察当前位置的分布。给定端点后运动是确定的；端点随机，当前位置就随机。

对于 $0\leq t<1$，独立配对还给出一个直观的密度表达式：

$$
p_t(x)
=\int
\frac{1}{(1-t)^d}
p_0\!\left(\frac{x-tx_1}{1-t}\right)
p_{\mathrm{data}}(x_1)\,dx_1.
$$

先固定数据端点 $x_1$，噪声被缩放、平移；再对所有数据端点混合。训练不需要计算这个积分，直接采样 $(X_0,X_1,t)$ 就能获得 $X_t$。

线性插值是一种路径选择；独立配对是另一项选择。即使端点分布不变，改变配对也可能改变中间分布。本文先把这两项都固定下来，文末再讨论配对。

接下来出现核心问题：**每对端点都有自己的速度，网络只看见 $(x,t)$，怎样学成一个统一的场？**

## 3. 核心：端点速度怎样变成统一的生成速度场？

### 3.1 同一个位置附近，标签为什么会有分歧？

想象两组端点：一条直线朝左上走，另一条朝右下走。它们可能在相同时间经过同一小片区域，却带着不同的速度标签。

连续空间中，“两个独立样本恰好落在完全相同的位置”通常是零概率事件。这里讨论的是给定位置的条件分布，直觉上可以先理解为：把时刻和位置限定在越来越小的邻域中，观察经过附近的速度。

网络收到的输入只有当前位置和时间：

$$
(X_t,t)\longmapsto v_\theta(X_t,t).
$$

它没有收到那次采样的 $X_0$ 和 $X_1$，因此无法根据被隐藏的端点身份，为同一个输入输出多个不同答案。

### 3.2 平方误差把答案定为条件期望

固定 $t$ 和位置 $x$，暂时把网络输出写成一个待选择的向量 $a$。它面对的局部回归问题是

$$
\min_{a\in\mathbb R^d}
\mathbb E\!\left[\|a-U\|^2\mid X_t=x\right].
$$

令

$$
m_t(x)=\mathbb E[U\mid X_t=x].
$$

展开平方：

$$
\begin{aligned}
\mathbb E[\|a-U\|^2\mid X_t=x]
&=\|a\|^2-2a^\top m_t(x)
  +\mathbb E[\|U\|^2\mid X_t=x]\\
&=\|a-m_t(x)\|^2
  +\mathbb E[\|U\|^2\mid X_t=x]-\|m_t(x)\|^2.
\end{aligned}
$$

后两项不依赖 $a$，所以最优输出为

$$
\boxed{
v_t^*(x)=\mathbb E[U\mid X_t=x].
}
$$

这就是**边缘速度场**。它把“端点对提供的速度”转成“当前位置应该使用的统一速度”。给定输入后的条件平均，也是平方回归的一般性质。

条件平均的权重不是均匀的。对于更可能经过 $(x,t)$ 的端点对，它们在平均中占据更大的比重。如果用 $\pi(dx_0,dx_1\mid X_t=x)$ 表示端点后验，那么

$$
v_t^*(x)
=\int (x_1-x_0)\,
\pi(dx_0,dx_1\mid X_t=x).
$$

独立配对只规定采样端点时的关系。**观察到中间位置以后，端点的后验通常已经相关。** 不能在这个条件期望里继续把 $X_0$ 和 $X_1$ 当成独立变量。

另一个有用的表达式来自插值恒等式。对 $t<1$，

$$
U=\frac{X_1-X_t}{1-t},
$$

因此

$$
v_t^*(x)
=\frac{\mathbb E[X_1\mid X_t=x]-x}{1-t}.
$$

这里出现了数据端点的后验均值，但网络最终学习的是当前位置的速度。生成图片还要经过整个积分过程。

### 3.3 参考轨迹是直线，生成轨迹为什么会弯？

参考运动沿每次选定的端点对前进：

$$
X_t=(1-t)X_0+tX_1.
$$

理想生成运动沿统一速度场前进：

$$
\frac{dY_t}{dt}=v_t^*(Y_t),\qquad Y_0\sim p_0.
$$

参考直线始终记得自己的两个端点；生成轨迹每到一个新位置，都重新查询该位置与时刻的条件平均速度。平均所涉及的端点后验随位置、时间改变，方向自然也可能改变。

更明确地说，在速度场可微时，生成轨迹的加速度为

$$
\frac{d^2Y_t}{dt^2}
=\partial_t v_t^*(Y_t)
+D_xv_t^*(Y_t)\,v_t^*(Y_t).
$$

其中 $D_xv$ 是速度场对位置的 Jacobian。第一项来自时间变化，第二项来自样本移动到别处后看到的空间变化。它们一般不会同时为零，所以参考运动中的常速度，不能推出生成运动也有常速度。

<figure class="math-figure">
  <a href="/images/flow-matching/paths.svg"><img src="/images/flow-matching/paths.svg" width="1200" height="625" alt="同一个二维双峰例子：左侧是独立端点之间的参考直线，右侧是从相同噪声点出发、沿解析条件平均速度场积分得到的弯曲轨迹；右侧终点通常不等于左侧配对的数据端点" /></a>
  <figcaption>图 1：两幅图使用相同的噪声起点。左侧随机配数据端点，右侧积分真实的条件平均速度场；颜色追踪起点，不表示右侧仍到达左侧对应的终点。图由解析二维例子数值计算得到，没有训练神经网络。</figcaption>
</figure>

图中的数据分布固定为两个高斯的等权混合：

$$
p_1(x)
=\frac12\mathcal N(x;m_1,\sigma^2I)
+\frac12\mathcal N(x;m_2,\sigma^2I),
$$

$$
m_1=(-2,0.8)^\top,\qquad
m_2=(2,-0.8)^\top,\qquad \sigma=0.4.
$$

后面的分布图仍使用这个例子。它让我们同时看见参考路径、生成路径和各时刻的概率分布。

### 3.4 保持边缘分布，不恢复原来的配对

理论要证明的是

$$
\operatorname{Law}(Y_t)=\operatorname{Law}(X_t)=p_t.
$$

这没有要求

$$
(Y_0,Y_1)\overset{d}{=}(X_0,X_1).
$$

左边的末端是初值经过确定性 ODE 后得到的结果；右边采用的是独立配对。在非退化的数据分布下，它们通常具有不同的联合分布。

例如，一份训练噪声这次被配到左侧的数据簇，下一次也可能被配到右侧。生成时不需要复现这项随机配对，只需要使所有起点最终到达两侧的比例、位置分布正确。

**平均的是同一时刻、同一位置下的瞬时速度。最终样本来自沿速度场的积分。** 将网络输出直接理解成“平均训练图片”，会丢掉位置依赖、时间依赖以及积分这三件事。第 6 节会看到，若把积分草率地压成一步，确实可能退化到数据均值。

## 4. 成立依据：为什么条件平均能搬运正确的分布？

条件平均目前只是一个最小化平方误差的答案。它是否真的把分布推向数据，还需要概率质量守恒来连接。

### 4.1 连续性方程在守恒什么？

取空间中的固定区域 $A$，其中的概率质量为

$$
\Pr(X_t\in A)=\int_Ap_t(x)\,dx.
$$

如果概率只随运动进出区域，没有凭空产生或消失，那么质量变化率等于流入减去流出：

$$
\frac{d}{dt}\int_Ap_t(x)\,dx
=-\int_{\partial A}p_t(x)v_t(x)\cdot n(x)\,dS.
$$

$n(x)$ 是边界的外法向量。速度朝外时，右侧为负，区域中的概率减少。使用散度定理，

$$
\int_{\partial A}p_tv_t\cdot n\,dS
=\int_A\nabla\cdot(p_tv_t)\,dx.
$$

因为上述等式对任意区域成立，就得到连续性方程：

$$
\boxed{
\partial_tp_t+\nabla\cdot(p_tv_t)=0.
}
$$

这里 $p_tv_t$ 是概率流密度。$\nabla\cdot$ 表示散度，即每个坐标方向净流出的总和：

$$
\nabla\cdot(p_tv_t)
=\sum_{j=1}^d\frac{\partial}{\partial x_j}
\left(p_t(x)v_t^{\,j}(x)\right).
$$

它是分布的偏微分方程；样本轨迹遵循的是常微分方程。两者描述同一次运输的不同层面。

### 4.2 用测试函数把参考运动接到连续性方程

直接对密度求导有时不方便。取任意光滑、紧支撑的测试函数 $\varphi:\mathbb R^d\to\mathbb R$，考察统计量

$$
\mathbb E[\varphi(X_t)]=\int\varphi(x)p_t(x)\,dx.
$$

“测试函数”可以理解为一种观察分布的方法：用不同的 $\varphi$ 去检测概率质量分布在何处。不能只检测均值或方差；这里要求对全部这样的测试函数成立。

参考运动满足 $\dot X_t=U$，所以在允许交换求导与期望时，链式法则给出

$$
\frac{d}{dt}\mathbb E[\varphi(X_t)]
=\mathbb E[\nabla\varphi(X_t)^\top U].
$$

接下来是关键的一步：$\nabla\varphi(X_t)$ 只依赖当前位置，因而可以先对 $X_t$ 取条件期望：

$$
\begin{aligned}
\mathbb E[\nabla\varphi(X_t)^\top U]
&=\mathbb E\!\left[
  \mathbb E[\nabla\varphi(X_t)^\top U\mid X_t]
  \right]\\
&=\mathbb E\!\left[
  \nabla\varphi(X_t)^\top\mathbb E[U\mid X_t]
  \right]\\
&=\int\nabla\varphi(x)^\top v_t^*(x)p_t(x)\,dx.
\end{aligned}
$$

所以，用条件平均速度替换每对端点的速度，不会改变任何这类统计量的瞬时变化率。再分部积分：

$$
\int\varphi(x)\partial_tp_t(x)\,dx
=-\int\varphi(x)\nabla\cdot\!\left(p_t(x)v_t^*(x)\right)\,dx.
$$

因此 $p_t$ 以弱意义满足

$$
\partial_tp_t+\nabla\cdot(p_tv_t^*)=0.
$$

这个证明依赖的是链式法则、条件期望和分部积分。它没有要求参考直线与生成轨迹逐条相同。Flow Matching 中从条件路径构造边缘场的结论，可以对照[原论文第 3 节与附录](https://arxiv.org/html/2210.02747v2)。

### 4.3 为什么能进一步得到 ODE 的分布？

设 $Y_t$ 是速度场 $v_t^*$ 的 ODE 解，记其分布为 $q_t$。对 $Y_t$ 重复同样的测试函数计算，得到

$$
\partial_tq_t+\nabla\cdot(q_tv_t^*)=0,
\qquad q_0=p_0.
$$

参考分布 $p_t$ 满足同一个方程、同一个初始分布。**在 ODE 流存在，以及相应连续性方程解唯一的条件下，**

$$
\boxed{q_t=p_t.}
$$

这才完成了逻辑连接：

$$
\text{参考插值}
\;\Longrightarrow\;
\text{条件平均速度}
\;\Longrightarrow\;
\text{同一个连续性方程}
\;\Longrightarrow\;
\text{相同的边缘分布}.
$$

附录 B 会给出一组足够条件，也会说明有限数据集、低维流形和 $t=1$ 端点为什么需要另外处理。网络只近似拟合 $v_t^*$ 时，上述等式也变成近似关系，不能把理想定理直接当作实际模型的零误差保证。

<figure class="math-figure">
  <a href="/images/flow-matching/marginals.svg"><img src="/images/flow-matching/marginals.svg" width="1200" height="650" alt="标准高斯到二维双峰分布在五个时刻的演化：上排为独立端点插值得到的样本，下排为沿真实条件平均场积分得到的样本；单点去向不同，但两排各时刻的分布相符" /></a>
  <figcaption>图 2：上排是端点插值，下排是 ODE 运输。两排使用相同的一批噪声起点；参考端点独立抽样。有限样本有采样波动，ODE 还有数值误差，但两排应接近各时刻同一分布。背景等高线来自已知的解析密度。</figcaption>
</figure>

### 4.4 同一分布路径可能有不同速度场

若另一个场 $w_t$ 满足

$$
\nabla\cdot(p_tw_t)=0,
$$

则 $v_t^*+w_t$ 和 $v_t^*$ 对应同一个连续性方程。直觉上，可以存在不改变当前密度的环流。

例如在二维标准高斯上，旋转场 $w(x)=(-x_2,x_1)^\top$ 不改变径向对称的密度。静止和旋转可以具有完全相同的边缘分布，却有不同轨迹。

因此，本文讨论的是**由指定配对与插值诱导，并由平方回归选出的那个场**，没有声称它是所有可行运输中的唯一速度场。

## 5. 训练：为什么简单的端点速度 MSE 就够了？

### 5.1 理想目标与可计算目标

如果能够直接计算边缘速度 $v_t^*$，理想训练目标是

$$
\mathcal L_{\mathrm{FM}}(\theta)
=\mathbb E_{t,X_t}
\left[\|v_\theta(X_t,t)-v_t^*(X_t)\|^2\right].
$$

本文默认时间独立地均匀采样：

$$
t\sim\mathcal U(0,1).
$$

但 $v_t^*$ 包含未知的端点后验，通常无法直接计算。实际使用的 Conditional Flow Matching 目标为

$$
\boxed{
\mathcal L_{\mathrm{CFM}}(\theta)
=\mathbb E_{t,X_0,X_1}
\left[\|v_\theta((1-t)X_0+tX_1,t)-(X_1-X_0)\|^2\right].
}
$$

右侧所有量都能由随机端点直接获得。这里的 CFM 指利用条件路径构造监督信号；此时还没有引入文本条件。[广义 CFM 论文](https://arxiv.org/html/2302.00482v3)讨论了从端点耦合构造训练目标的形式。

### 5.2 误差分解为什么让两个目标等价？

为了简化记号，写成

$$
V=v_\theta(X_t,t),\qquad M=v_t^*(X_t).
$$

有

$$
V-U=(V-M)+(M-U).
$$

平方展开后，

$$
\mathbb E\|V-U\|^2
=\mathbb E\|V-M\|^2
+\mathbb E\|M-U\|^2
+2\mathbb E[(V-M)^\top(M-U)].
$$

记 $\mathcal G=\sigma(X_t,t)$，即当前位置和时间包含的信息。$V-M$ 对 $\mathcal G$ 可测，且

$$
\mathbb E[M-U\mid\mathcal G]=0.
$$

所以交叉项为

$$
\begin{aligned}
\mathbb E[(V-M)^\top(M-U)]
&=\mathbb E\!\left[
(V-M)^\top\mathbb E[M-U\mid\mathcal G]\right]\\
&=0.
\end{aligned}
$$

由此得到

$$
\boxed{
\mathcal L_{\mathrm{CFM}}(\theta)
=\mathcal L_{\mathrm{FM}}(\theta)
+\mathbb E\|U-v_t^*(X_t)\|^2.
}
$$

最后一项由数据、配对和路径决定，与网络参数 $\theta$ 无关。因此两个**总体目标**相差一个常数；在梯度与期望可以交换的条件下，

$$
\boxed{
\nabla_\theta\mathcal L_{\mathrm{CFM}}
=\nabla_\theta\mathcal L_{\mathrm{FM}}.
}
$$

这不是说每个训练样本的梯度都相同。端点速度是带有条件方差的监督信号，有限 minibatch 的梯度会波动，但其期望对应同一个总体梯度。

### 5.3 为什么 loss 不一定降到零？

对固定的 $(X_t,t)$，不同端点对可能给出不同的 $U$。即使网络已经精确等于 $v_t^*$，依然会留下

$$
\mathcal L_{\mathrm{CFM}}^{\min}
=\mathbb E\!\left[
\operatorname{tr}\operatorname{Cov}(U\mid X_t,t)
\right].
$$

这是回归标签不可由输入完全确定带来的误差。它不表示网络仍然没有学会边缘速度，也不能直接拿它解释生成图片的质量。

这个结论还给出一个实用提醒：换路径、换时间权重或换配对之后，loss 的基线也可能变化。不能只比较训练损失数值的大小，就断言某个方法生成得更好。

### 5.4 最小训练循环

下面是无条件版本的 PyTorch 风格伪代码。网络输出与样本同形状，示例用每个样本的坐标误差之和，对应上面的欧氏范数平方。

~~~python
for x1 in data_loader:
    x0 = torch.randn_like(x1)
    t = torch.rand(x1.shape[0], device=x1.device)
    t_view = t.reshape(-1, *([1] * (x1.ndim - 1)))

    xt = (1 - t_view) * x0 + t_view * x1
    target_velocity = x1 - x0
    predicted_velocity = velocity_net(xt, t)

    squared_error = (predicted_velocity - target_velocity).square()
    loss = squared_error.flatten(1).sum(1).mean()

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
~~~

训练时直接计算 $X_t$，没有沿当前网络的 ODE 从 $0$ 积分到 $t$，也不必穿过一个求解器反向传播。这就是这里的 **simulation-free training**。

它描述训练目标的计算方式。生成阶段仍要沿学到的速度场求解 ODE。

## 6. 生成：从新噪声出发，怎样得到新样本？

### 6.1 把连续时间的 ODE 离散化

训练完成后，抽取一份没有参与那次端点配对的新噪声：

$$
y_0\sim\mathcal N(0,I).
$$

取时间网格 $0=t_0<t_1<\cdots<t_N=1$，记 $h_k=t_{k+1}-t_k$。由积分形式，

$$
y_{t_{k+1}}
=y_{t_k}+\int_{t_k}^{t_{k+1}}v_\theta(y_s,s)\,ds.
$$

Euler 方法用区间左端点的速度近似整个积分：

$$
\boxed{
y_{k+1}=y_k+h_kv_\theta(y_k,t_k).
}
$$

它只需要当前样本、当前时间和速度网络，完全不需要预先知道最终图片。方向由网络在每个位置给出。

### 6.2 时间输入与随机性分别负责什么？

同一个位置在早期可能需要向内聚集，在后期可能需要向某个数据簇分流，所以一般不能省掉时间输入。

对于确定性速度网络与确定性 ODE 求解器，固定初始噪声和其他条件，就固定了一次采样的结果。该设定下的生成多样性来自不同的初始噪声；一些系统另外加入随机采样步骤，属于不同的采样设定。

### 6.3 线性参考路径为什么不保证一步生成？

本文的独立配对满足

$$
v_0^*(x)
=\mathbb E[X_1-X_0\mid X_0=x]
=\mu_1-x,
\qquad \mu_1=\mathbb E[X_1].
$$

如果从 $0$ 到 $1$ 只做一步 Euler，即使在起点使用精确的端点速度，也会得到

$$
y_1^{\mathrm{one\ step}}
=y_0+v_0^*(y_0)=\mu_1.
$$

所有噪声都被送到数据均值。对于本文均值为零的双峰例子，这一步会把所有样本送到两簇之间的原点。

这不是条件平均的运输定理失效，而是**用起点速度替代整个时间区间的积分失效**。后续时刻的场已经变化，一步 Euler 把这些变化全部省略了。

要做到可靠的一步或少步生成，还需要额外的路径设计、训练或蒸馏。训练端点间画的是直线，本身不提供这样的保证。

### 6.4 模型误差与积分误差要分开

把理想 ODE 解记为 $y_t^*$，精确积分学习到的场得到 $y_t^\theta$，数值求解器输出记为 $\widehat y_k$。有

$$
\|\widehat y_N-y_1^*\|
\leq
\underbrace{\|\widehat y_N-y_1^\theta\|}_{\text{numerical error}}
+
\underbrace{\|y_1^\theta-y_1^*\|}_{\text{model error}}.
$$

第一项来自数值离散化；第二项来自网络速度与理想速度的差别。在足够光滑、稳定的条件下，Euler 的单步局部截断误差为 $O(h^2)$，固定区间上的全局误差为 $O(h)$。

提高求解精度主要压低第一项。若网络已经把速度方向预测错，再精确地求解这个错误的场，也不会自动修复第二项。附录 B 会给出一个 Grönwall 误差界，并解释它与训练 MSE 之间的距离。

### 6.5 最小采样循环

~~~python
velocity_net.eval()
with torch.no_grad():
    y = torch.randn(batch_size, channels, height, width, device=device)
    times = torch.linspace(0, 1, steps + 1, device=device)

    for k in range(steps):
        t = times[k].expand(batch_size)
        dt = times[k + 1] - times[k]
        velocity = velocity_net(y, t)
        y = y + dt * velocity

    generated_samples = y
~~~

实际求解器可以采用不同阶数和自适应步长。比较采样成本时，还应比较网络调用次数：一个高阶步骤可能调用多次速度网络，“步数相同”不一定意味着计算量相同。

## 7. 落到生图：latent、文本与速度网络怎样组成系统？

### 7.1 训练时，每个数学对象对应什么？

考虑一个典型的 latent 文生图系统。训练数据是一对图片与文字描述 $(I,\text{prompt})$。

图像编码器把图片转到 latent 空间，文本编码器提供条件：

$$
z_1=E(I),\qquad c=T(\text{prompt}).
$$

这里的小写表示已经抽到的具体训练样本。若编码器采用随机采样，则把这次采样的结果作为 $z_1$；模型所需的 latent 缩放、平移等约定也包含在 $E$ 中。

以下将图像编码器和文本编码器视为固定模块，只训练速度网络。这样，数据路径和回归标签都不依赖速度网络参数，前面的梯度等价论证可以直接使用；若联合训练编码器，则需要重新分析参数对路径与条件的影响。

然后采样同形状噪声并插值：

$$
z_0\sim\mathcal N(0,I),\qquad
z_t=(1-t)z_0+tz_1.
$$

训练速度网络：

$$
\boxed{
\mathcal L(\theta)
=\mathbb E
\left[
\|v_\theta(z_t,t,c)-(z_1-z_0)\|^2
\right].
}
$$

期望覆盖图文对、噪声、时间，以及编码器可能引入的随机性。噪声独立于图文对，而图片与文本显然相互关联。

第 3–5 节的推导可以在每个文本条件下重新进行。相应的理想场为

$$
v_t^*(z,c)
=\mathbb E[Z_1-Z_0\mid Z_t=z,C=c].
$$

它搬运的是该条件下的 latent 分布：

$$
p_t(z\mid c),\qquad
p_0(z\mid c)=\mathcal N(0,I).
$$

“给定一对端点构造条件路径”与“给定文字描述生成图片”是两层不同的条件。前者让训练标签可计算；后者决定这次想生成什么。

### 7.2 推理时，一段 prompt 怎样走到图片？

固定输入文字，得到条件 $c$；从新 latent 噪声出发，求解

$$
\frac{d\hat z_t}{dt}=v_\theta(\hat z_t,t,c),
\qquad \hat z_0\sim\mathcal N(0,I).
$$

得到 $\hat z_1$ 后，再解码回像素空间：

$$
\boxed{\hat I=D(\hat z_1).}
$$

<figure class="math-figure">
  <a href="/images/flow-matching/text-to-image.svg"><img src="/images/flow-matching/text-to-image.svg" width="1200" height="620" alt="训练流程：图文对分别经图像编码器和文本编码器，图片 latent 与噪声插值，速度网络回归端点差；推理流程：固定文本条件，ODE 求解器反复调用速度网络更新新噪声，最终经解码器生成图片" /></a>
  <figcaption>图 3：训练时可以看见图片端点并制造速度标签；推理时固定文本，只携带当前 latent 沿速度场前进。</figcaption>
</figure>

| 组件 | 职责 |
| --- | --- |
| 图像编码器 / 解码器 $E,D$ | 在图像与 latent 之间转换 |
| 文本编码器 $T$ | 将 prompt 转成可供网络使用的文本条件 |
| DiT 等速度网络 $v_\theta$ | 根据当前位置、时间和文本预测瞬时速度 |
| ODE 求解器 | 多次调用速度网络，累积位移，更新 latent |

若 latent 的形状是 $B\times C\times H\times W$，最终速度输出也应具有这个形状。网络内部可以将 latent 分块、展平成 token，与文本做注意力交互；输出还需要还原到对应的 latent 坐标。它预测的是每个坐标的变化率。

Flow Matching 描述路径与训练目标，DiT 描述网络结构，两者属于不同层面。latent 系统是否能生成高质量图片，还取决于数据、编码器和网络的近似能力；即使 latent 的分布运输完全正确，解码器本身也可能引入重建误差。

### 7.3 CFG 在哪里接入？

若训练时通过一定概率丢弃文本，使同一网络也能预测无条件速度，就可以在推理时组合两次预测：

$$
v_{\mathrm{CFG}}(z,t,c)
=v_\theta(z,t,\varnothing)
+s\left[
v_\theta(z,t,c)-v_\theta(z,t,\varnothing)
\right].
$$

$s=1$ 时使用条件速度，$s=0$ 时使用无条件速度；$s>1$ 则沿条件与无条件预测的差进一步外推。这会改变实际积分的场，也带来额外网络计算。

不能把使用 CFG 后的结果，直接等同于未经修改的条件场精确采样 $p_1(z\mid c)$ 的结论。CFG 的强度与画面表现需要另外评估。这里使用的是[Classifier-Free Guidance](https://arxiv.org/abs/2207.12598)的条件与无条件预测组合思想，具体网络结构和实现另文展开。

## 附录 A：条件期望与平方误差分解

### A.1 把时间也放进条件信息

令 $T$ 是随机训练时间，与端点独立，定义

$$
Z=(X_T,T),\qquad
\mathcal G=\sigma(Z),\qquad
M=\mathbb E[U\mid\mathcal G].
$$

此处 $Z$ 只是输入信息的合并记号，与第 7 节的图像 latent 无关。若 $\mathbb E\|U\|^2<\infty$，条件期望 $M$ 是所有 $\mathcal G$ 可测、平方可积向量中对 $U$ 的最优平方逼近。

它的核心性质是：对任意平方可积、$\mathcal G$ 可测向量 $H$，

$$
\begin{aligned}
\mathbb E[H^\top(U-M)]
&=\mathbb E\!\left[
H^\top\mathbb E[U-M\mid\mathcal G]
\right]\\
&=0.
\end{aligned}
$$

这就是正交性。取 $H=V-M$，便得到正文中交叉项为零的完整理由。不是假定误差随机抵消，而是条件期望的定义保证它对已知信息正交。

从几何上看，$\mathcal G$ 可测向量构成 $L^2$ 中的一个闭子空间，$M$ 是 $U$ 在该子空间上的正交投影。平方误差分解对应勾股定理：

$$
\|V-U\|_{L^2}^2
=\|V-M\|_{L^2}^2+\|U-M\|_{L^2}^2.
$$

### A.2 直接核对总体梯度

设网络输出对参数的 Jacobian 为 $J_\theta V$。当可微性、可积性允许交换梯度与期望时，

$$
\nabla_\theta\mathcal L_{\mathrm{CFM}}
=2\mathbb E[(J_\theta V)^\top(V-U)].
$$

$J_\theta V$ 也只依赖 $Z$，所以

$$
\begin{aligned}
\mathbb E[(J_\theta V)^\top(V-U)]
&=\mathbb E\!\left[
(J_\theta V)^\top
\mathbb E[V-U\mid Z]
\right]\\
&=\mathbb E[(J_\theta V)^\top(V-M)].
\end{aligned}
$$

右侧正是 $\frac12\nabla_\theta\mathcal L_{\mathrm{FM}}$。有限网络函数类中，两个总体目标也具有相同的极小点，但极小点未必能够使 $V=M$：模型容量不足和优化未收敛，都会留下额外误差。

### A.3 时间采样与损失权重必须用同一约定

正文固定均匀时间、单位权重。如果改成时间密度 $\rho(t)$ 和非负权重 $w(t)$，

$$
\mathcal L_{\mathrm{CFM}}^{\rho,w}
=\mathbb E_{T\sim\rho}
\left[w(T)\|V-U\|^2\right],
$$

只要 FM 目标也使用同样的采样与权重，仍有

$$
\mathcal L_{\mathrm{CFM}}^{\rho,w}
=\mathcal L_{\mathrm{FM}}^{\rho,w}
+\mathbb E\!\left[w(T)\|U-M\|^2\right].
$$

在采样密度与权重都严格为正的时间范围内，逐点最优预测仍是原条件期望；若某些时间区间没有被采样或权重为零，则那些区间的速度不再受这个目标约束。若从 $\rho$ 采样却想估计均匀时间目标，需要相应的重要性权重 $1/\rho(T)$，并保证支持覆盖和可积性。

在坐标上取平均而不是求和，只会给固定维度下的损失乘一个常数。按样本内容、端点身份改变权重，则不能直接套用上述逐时间权重的结论，条件回归目标可能随之改变。

### A.4 一个可以直接验算的回归例子

取独立的 $X_0,X_1\sim\mathcal N(0,I)$。虽然两端分布相同，独立插值的中间方差仍为

$$
a_t=(1-t)^2+t^2,\qquad X_t\sim\mathcal N(0,a_tI).
$$

有

$$
\operatorname{Cov}(U,X_t)=(2t-1)I,
\qquad
v_t^*(x)=\frac{2t-1}{a_t}x.
$$

ODE 的解可以直接写出：

$$
Y_t=\sqrt{a_t}\,Y_0,
$$

因为

$$
\frac{d}{dt}\sqrt{a_t}
=\frac{2t-1}{\sqrt{a_t}}.
$$

其分布确实是 $\mathcal N(0,a_tI)$，而 $Y_1=Y_0$。生成耦合是恒等映射，训练耦合却是独立配对。

在 $t=\frac12$ 时，$U$ 与 $X_t$ 的协方差为零；二者联合高斯，所以独立。于是

$$
v_{1/2}^*(x)=0,\qquad
\operatorname{Cov}(U\mid X_{1/2})=2I.
$$

此时边缘速度已经完全正确，但回归标签仍有非零方差。它同时验证了“正确的场不恢复原配对”和“正确的场不意味着 CFM loss 为零”。

## 附录 B：连续性方程与 ODE 的适用条件

### B.1 不依赖密度的弱形式

为避免一开始就要求 $p_t$ 具有光滑密度，先把参考分布写成概率测度 $\mu_t=\operatorname{Law}(X_t)$。

对时间与空间都光滑、空间紧支撑的 $\psi(t,x)$，链式法则给出

$$
\frac{d}{dt}\psi(t,X_t)
=\partial_t\psi(t,X_t)
+\nabla_x\psi(t,X_t)^\top U.
$$

取期望，再对时间积分：

$$
\begin{aligned}
&\int\psi(1,x)\,\mu_1(dx)
-\int\psi(0,x)\,\mu_0(dx)\\
&\quad=\int_0^1\int
\left[
\partial_t\psi(t,x)
+\nabla_x\psi(t,x)^\top v_t^*(x)
\right]\mu_t(dx)\,dt.
\end{aligned}
$$

这里仍然只是把 $U$ 替换为 $\mathbb E[U\mid X_t]$。如果 $\mathbb E\|U\|<\infty$，测试函数及其导数有界，便有合适的支配条件进行这些交换；平方回归则通常进一步假设端点二阶矩有限。

这就是连续性方程的弱形式。若 $\mu_t(dx)=p_t(x)\,dx$，且有足够正则性，再对时间和空间分部积分，就回到正文的偏微分方程。

条件期望只在 $\mu_t$ 几乎处处定义。在零概率位置怎样延拓速度场，不影响这个弱形式，但可能影响能否构造全局良好的 ODE。因此“条件平均有定义”和“存在唯一、稳定的全局流”需要分开讨论。

### B.2 一组足够条件，以及唯一性怎样使用

下面是一组便于理解的充分条件，并非必要条件。假设能为 $v_t^*$ 选取一个版本，使它对时间可测、对空间连续，并满足

$$
\|v_t^*(x)-v_t^*(y)\|
\leq L(t)\|x-y\|,
$$

$$
\|v_t^*(x)\|\leq a(t)(1+\|x\|),
\qquad L,a\in L^1([0,1]).
$$

第一项控制相邻样本的速度差，第二项排除有限时间爆炸。此时可以建立存在唯一的绝对连续 ODE 解，并在有限一阶矩、窄连续的概率测度解类中得到运输方程的唯一性。

令 $\Phi_{s,t}$ 表示从时刻 $s$ 到 $t$ 的流。对固定终点测试函数 $f$，定义

$$
g(s,x)=f(\Phi_{s,t}(x)).
$$

在足够光滑的情形下，$g$ 满足反向运输方程

$$
\partial_sg(s,x)+v_s^*(x)\cdot\nabla_xg(s,x)=0.
$$

将它代入任意连续性方程解的弱形式，得到

$$
\int f(x)\,\mu_t(dx)
=\int f(\Phi_{0,t}(x))\,\mu_0(dx).
$$

右侧只取决于初始分布和流，所以解必须是 $(\Phi_{0,t})_\#\mu_0$。较弱正则性下，需要通过逼近处理测试函数；这里用光滑情形展示唯一性为什么足以完成正文的结论。

### B.3 密度沿轨迹怎样变化？

若场对空间可微，令

$$
J_t(x)=D_x\Phi_{0,t}(x).
$$

对 ODE 关于初值求导：

$$
\frac{dJ_t}{dt}
=D_xv_t^*(\Phi_{0,t}(x))J_t,
\qquad J_0=I.
$$

Jacobi 行列式公式给出

$$
\frac{d}{dt}\log|\det J_t|
=\operatorname{tr}D_xv_t^*(\Phi_{0,t}(x))
=\nabla\cdot v_t^*(\Phi_{0,t}(x)).
$$

再用概率质量守恒，

$$
p_t(\Phi_{0,t}(x))\,|\det J_t(x)|=p_0(x).
$$

取对数并求导：

$$
\boxed{
\frac{d}{dt}\log p_t(Y_t)
=-\nabla\cdot v_t^*(Y_t).
}
$$

速度场局部向外发散时，同一小团概率占据的体积变大，密度下降；局部汇聚时则相反。这也可以由展开连续性方程，再沿轨迹使用链式法则得到。

Flow Matching 的回归训练无需计算这个 Jacobian 行列式。它出现在这里，是为了把轨迹、体积变化与密度演化连接起来。

### B.4 端点为什么可能出问题？

若把有限数据集严格视为若干 Dirac 质量的混合，$p_{\mathrm{data}}$ 是离散测度。一个在闭区间上足够正则、可逆的流，不能把绝对连续的高斯精确压成若干点质量。

最简单的例子是 $X_1=0$：

$$
X_t=(1-t)X_0,\qquad
v_t^*(x)=-\frac{x}{1-t},\qquad t<1.
$$

对应解为 $Y_t=(1-t)Y_0$，其分布在 $t\uparrow1$ 时收敛到 $\delta_0$，但速度场的空间 Lipschitz 常数为

$$
L(t)=\frac{1}{1-t},
\qquad
\int_0^1L(t)\,dt=\infty.
$$

它不满足上一节在闭区间上的充分条件。这个例子说明：开区间内的正确运输，可以伴随奇异的终点极限。

常见的数学处理包括为数据加入少量平滑噪声、先证明 $[0,1-\varepsilon]$ 内的结论，再分析端点的弱极限。实际采用提前停止或保留终点噪声时，终点分布相应改变，不能仍然写成与原数据分布严格相等。低维流形上的数据也有类似问题。

另外，均匀抽样时间几乎不会恰好抽到端点。训练损失约束的是时间上的几乎处处行为，不会单独为两个端点提供任意强度的正则性保证。

### B.5 速度误差如何累积成轨迹误差？

取相同初值，令 $y_t^*$ 沿理想场运行，$y_t^\theta$ 沿学习场精确运行。假设理想场具有空间 Lipschitz 常数 $L(t)$，定义沿学习轨迹的速度误差

$$
\epsilon(t)
=\|v_\theta(y_t^\theta,t)-v_t^*(y_t^\theta)\|.
$$

将两个 ODE 相减，并加减 $v_t^*(y_t^\theta)$，可得

$$
\frac{d}{dt}\|y_t^\theta-y_t^*\|
\leq L(t)\|y_t^\theta-y_t^*\|+\epsilon(t)
$$

在相应的几乎处处意义下成立。由 Grönwall 不等式，

$$
\boxed{
\|y_1^\theta-y_1^*\|
\leq
\int_0^1
\exp\!\left(\int_s^1L(r)\,dr\right)\epsilon(s)\,ds.
}
$$

误差不仅逐步累积，还可能被场的空间变化放大。若积分的是一个不稳定或端点奇异的场，不能随意把这个界当成有限常数。

还需要注意：训练 MSE 在参考分布 $p_t$ 下取平均，而这里的 $\epsilon(t)$ 沿模型自己的轨迹取值。小的平均训练误差，不自动等于每条生成轨迹上的一致小误差；若要证明分布距离的误差界，还需要额外的稳定性、覆盖与可积性条件。

### B.6 二维配图的解析场从哪里来？

图 1–2 的混合高斯例子可以直接算出速度，因此不需要先训练一个网络来充当“真值”。

令 $K\in\{1,2\}$ 是等概率的混合分量，条件于 $K=k$，

$$
X_1\mid K=k\sim\mathcal N(m_k,\sigma^2I),
\qquad X_0\perp(X_1,K).
$$

记

$$
s_t^2=(1-t)^2+t^2\sigma^2,
\qquad
b_t=t\sigma^2-(1-t).
$$

则

$$
X_t\mid K=k\sim\mathcal N(tm_k,s_t^2I),
$$

$$
\operatorname{Cov}(U,X_t\mid K=k)=b_tI.
$$

由联合高斯的条件均值公式，

$$
\mathbb E[U\mid X_t=x,K=k]
=m_k+\frac{b_t}{s_t^2}(x-tm_k).
$$

分量后验权重为

$$
r_k(x,t)
=\frac{\exp\!\left(-\frac{\|x-tm_k\|^2}{2s_t^2}\right)}
{\sum_{j=1}^2\exp\!\left(-\frac{\|x-tm_j\|^2}{2s_t^2}\right)}.
$$

再取一次条件平均，得到绘图使用的速度场：

$$
v_t^*(x)
=\sum_{k=1}^2r_k(x,t)
\left[m_k+\frac{b_t}{s_t^2}(x-tm_k)\right].
$$

在这个例子里，$\sigma>0$，所以整个时间区间都有 $s_t^2>0$，避开了点质量终点的奇异性。图中的 ODE 采用固定步长 RK4 数值积分；密度等高线则直接由两个高斯的混合计算。

## 文末扩展：端点配对怎样影响运输？

正文一直固定独立耦合

$$
\pi_{\mathrm{ind}}(dx_0,dx_1)=p_0(dx_0)p_1(dx_1).
$$

更一般地，可以选任意具有这两个边缘分布的耦合 $\pi\in\Pi(p_0,p_1)$，再定义同样的线性插值。第 4 节的测试函数论证仍然成立，但路径 $p_t$、条件平均速度和标签方差都可能改变。

二次代价的最优传输耦合求解

$$
\pi_{\mathrm{OT}}
\in\arg\min_{\pi\in\Pi(p_0,p_1)}
\mathbb E_\pi\|X_1-X_0\|^2.
$$

独立配对中的每条线段，确实是那一对端点之间的直线路径；但端点本身可能配得很远，整个配对不一定最省运输代价。**两点间连直线与两个分布之间的整体最优传输，是两个不同问题。**

例如附录 A 的同分布高斯例子，独立配对的期望端点代价为 $2d$；若让 $X_1=X_0$，代价为零。两种配对画的都可以是直线，整体运输代价却完全不同。

实践中的 minibatch OT 利用有限批次近似端点匹配，不应直接等同于总体分布的精确 OT。相关构造可见 [OT-CFM](https://arxiv.org/html/2302.00482v3)。

[Rectified Flow](https://arxiv.org/abs/2209.03003)与本文的线性插值回归有紧密联系；reflow 则进一步利用已有流生成新的端点配对，再训练新的场，以改善轨迹形状和粗步长采样。它们没有把“独立配对的每条参考线段是直线”自动升级为“一次训练后所有生成轨迹都直”。

理解到这里，再读路径设计、OT coupling、Rectified Flow 和少步蒸馏，就能分清它们分别改动了什么：配对、概率路径、回归目标，或求解时实际使用的速度。

延伸阅读：[Flow Matching Guide and Code](https://arxiv.org/abs/2412.06264)、[官方代码与示例](https://facebookresearch.github.io/flow_matching/)。本文的二维图按附录 B 的公式独立计算，推导统一采用噪声到数据的时间方向。
