---
title: "图像生成模型简介"
date: 2026-07-10
tags: [图像生成, 深度学习]
draft: false
---

## 一、模型结构总览

### 1\.1 生成流程概述

图像生成模型的核心任务是：给定一段文字描述（`prompt`），生成对应的图片。整个流程涉及三个核心组件，分工明确：

1. <strong>Text Encoder（文本编码器）</strong>：理解用户输入的文字，提取语义信息，转化为模型能处理的向量

2. <strong>DIT （扩散模型）</strong>：根据语义向量，从随机噪声中逐步还原出图片——这是最核心的生成步骤

3. <strong>VAE Decoder（解码器）</strong>：把模型内部的压缩图片翻译成人眼可见的像素图片



下面图片展示了完整的模型结构：

[![image\.png](/images/image-generation-models/image-11.png)](/images/image-generation-models/image-11.png)



### 1\.2 VAE（Variational Autoencoder，变分自编码器）— 图片压缩器

<strong>VAE（Variational Autoencoder，变分自编码器）</strong>是所有主流图像生成模型的第一个组件，负责将图片在「像素空间」和「潜空间（Latent Space）」之间转换。

<strong>一句话理解：</strong>VAE 就像图片的「智能 ZIP 压缩」——把一张高清大图压缩成一个小得多的数字摘要，保留核心信息，去掉大量冗余。模型在压缩后的空间里学习和创作，最后再解压还原成图片。



#### 为什么需要压缩？——图片的信息密度极低

[![image\.png](/images/image-generation-models/image-21.png)](/images/image-generation-models/image-21.png)

- 以一张草地和蓝天的风景图为例：图片下方是绿色草地覆盖在左高右低的山坡上，上方是蓝天和连绵不断的白云

- <strong>一张 70KB 的图片 ≈ 3\.5 万字</strong>——但大部分像素都是相似颜色的重复，信息密度极低



- <strong>压缩的意义：</strong>提高信息密度，方便模型学习。VAE 将真实的图像数据分布压缩为<strong>高斯分布（Gaussian Distribution）</strong>——在已知均值和方差的情况下，高斯分布的熵（不确定性）是所有分布中最大的，能包含最多的可能状态，是最「通用」的压缩目标。

- <strong>不压缩会怎样？</strong>训练相同分辨率的图片，需要消耗更大的算力和更长的时间，成本极高：

- 像素空间维度：1024 × 1024 × 3 = <strong>3,145,728</strong> 个数值

- 压缩以后：64 × 64 × 4 = <strong>16,384</strong> 个数值，<strong>压缩比约 192:1</strong>



#### 关键概念：Latent（潜变量）

<strong>Latent（潜变量）</strong>：VAE 编码后得到的向量矩阵，符合高斯分布。可以理解为图片的「精华摘要」——丢掉了逐像素的冗余，只保留了有意义的特征。等价于 NLP 中的 `embedding`。

[![image\.png](/images/image-generation-models/image-06.png)](/images/image-generation-models/image-06.png)



#### 卷积（Convolution）— VAE 内部的压缩手段

<strong>卷积（Convolution）</strong>是 VAE 内部实现压缩的核心操作。图像中相邻像素高度相关（天空连片蓝、皮肤连片肤色），卷积通过局部加权求和，把这种空间冗余概括为更紧凑的表示——相当于把图片从「逐像素描述」变成「区域级描述」。

[![image\.png](/images/image-generation-models/image-08.png)](/images/image-generation-models/image-08.png)



### 1\.3 Text Encoder（文本编码器）— 理解用户意图的大脑

<strong>Text Encoder（文本编码器）</strong>：把用户的文字输入转化为模型能理解的高维语义向量，作为图像生成的条件。

<strong>一句话理解：</strong>Text Encoder 是「大脑」，DIT 是「手」。大脑负责理解用户想要什么，手负责画出来。两者缺一不可。Text Encoder 的能力决定了模型对 prompt 的理解深度。Encoder 不够强 → 无法正确理解复杂描述（多人物、特定姿态、细节要求）→ 生成结果偏离用户意图。



<strong>举例：</strong>用户输入「一只威严的龙站在中世纪城堡上」，Text Encoder 不只是逐词理解，而是解析出：主体（西方龙、双翼、鳞片）、姿态（站立、前爪搭边缘）、背景（哥特式城堡）、氛围（黄昏、戏剧性光影）。这些语义信息作为 embedding 输入给 DIT。

### 1\.4 Diffusion（扩散）

<strong>Diffusion（扩散）</strong>：图像生成的核心机制——通过迭代去噪，从随机噪声中还原图片。

<strong>DDPM（Denoising Diffusion Probabilistic Models，去噪扩散概率模型）\[1\]</strong>定义了这个过程的数学框架：

- <strong>训练阶段：</strong>对真实图片逐步加噪（分 1000 步加到纯高斯噪声），让模型学习每一步如何去噪

- <strong>生成阶段：</strong>从纯噪声出发，反向跑去噪过程，逐步还原出图片（实际推理 30\-50 步即可）



#### Diffusion vs NTP（Next Token Prediction）

<strong>NTP（Next Token Prediction，下一个 token 预测）</strong>是 LLM 的生成方式——一个 token 一个 token 自回归生成。

- <strong>LLM</strong>：通过 NTP 逐个 token 顺序生成，像写文章一个字一个字写

- <strong>Diffusion</strong>：预测每步加入的噪声残差，迭代 30\-50 步逐步还原全局图像，像从模糊照片逐渐变清晰

<strong>为什么需要多步？</strong>单步预测太难——模型无法一步从噪声直接还原出完整图片。多步迭代等同于 LLM 的 <strong>CoT（Chain\-of\-Thought，思维链）</strong>——用更多算力换更好效果。

[![image\.png](/images/image-generation-models/image-05.png)](/images/image-generation-models/image-05.png)

#### 相关公式

以下是 DDPM 的核心数学公式（供有兴趣的同学参考，跳过不影响理解）：

[![image\.png](/images/image-generation-models/image-03.png)](/images/image-generation-models/image-03.png)

[![image\.png](/images/image-generation-models/image-10.png)](/images/image-generation-models/image-10.png)

[![image\.png](/images/image-generation-models/image-07.png)](/images/image-generation-models/image-07.png)

[![image\.png](/images/image-generation-models/image-02.png)](/images/image-generation-models/image-02.png)

[![image\.png](/images/image-generation-models/image-13.png)](/images/image-generation-models/image-13.png)

[![image\.png](/images/image-generation-models/image-12.png)](/images/image-generation-models/image-12.png)

[![image\.png](/images/image-generation-models/image-19.png)](/images/image-generation-models/image-19.png)

### 1\.5 DIT（Diffusion Transformer，扩散 Transformer）— 画图的手

<strong>DIT（Diffusion Transformer，扩散 Transformer）</strong>：负责实际的图像生成过程——根据 Text Encoder 提供的语义条件，从噪声中逐步还原出图片。

<strong>一句话理解：</strong>DIT 基于 Transformer 架构（和 LLM 相同的底层架构），通过注意力机制处理图像中不同区域之间的关系。它是模型的核心「引擎」，参数量和训练数据量直接决定生成质量上限。

#### DIT vs LLM 对比

DIT 和 LLM 都基于 Transformer 架构，但在输入输出和训练目标上有显著区别：

- <strong>LLM</strong>：输入是 token 序列，输出是下一个 token 的概率（NTP），自回归逐个生成

- <strong>DIT</strong>：输入是加了噪声的图像 latent \+ 文本 embedding，输出是噪声残差的预测，全局同时生成

[![image\.png](/images/image-generation-models/image-17.png)](/images/image-generation-models/image-17.png)

[![image\.png](/images/image-generation-models/image-09.png)](/images/image-generation-models/image-09.png)



### 1\.6 CFG（Classifier\-Free Guidance，无分类器引导）— 条件控制\[2\]

<strong>CFG（Classifier\-Free Guidance，无分类器引导）</strong>：解决「如何根据文字/图片条件生成图片，而不是随机生成」的核心技术。

<strong>一句话理解：</strong>CFG 是控制模型「多大程度听从你的指令」的旋钮。`guidance_scale` 越高，生成结果越贴近 prompt，但多样性/美观度下降。

<strong>原理：</strong>同时训练有条件和无条件的去噪，推理时用两者的差值放大条件的影响。

<strong>与我们工作的关系：</strong>推理时的重要超参数。guidance\_scale 调得太高会出现过饱和/不自然的问题，太低则不听指令，是一个经验参数，目前大部分模型取值范围在3\-10

[![image\.png](/images/image-generation-models/image-24.png)](/images/image-generation-models/image-24.png)

### 1\.7 图片编辑（Image Editing）

图片编辑将生成的条件从纯文字扩展到「图片 \+ 文字」：

- 图片 \+ 文字输入 → Text Encoder / MLLM → 统一语义空间的 embedding

- VAE 将参考图片编码到 latent 空间，和文本 embedding 一起作为条件输入

- <strong>可推广到任意条件：</strong>文本、参考图、姿态骨架、深度图等



## 二、训练（Training）

### 2\.1 预训练（Pre\-training）— 让模型学会画画

预训练使用 <strong>Billion 级别</strong>的图文对（pair）数据，经过细致筛选，目的是让模型学会「画画」这个基本能力。

<strong>DDPM 训练过程：</strong>在实际训练中，一般设定 1000 步模拟加噪过程，随机抽取其中一步让模型预测噪声残差。



#### <strong>Benchmark如何确定</strong>

- 模型最终会成为benchmark的形状

    - 符合业务的分布

        - 领域覆盖：如果产品主要生成漫画，benchmark就是漫画case

        - 难度分布：包含简单、中等、困难样本的合理配比

        - 长尾场景：特别关注低频但重要的场景（如特定风格、特殊构图）

    - 符合对"好"图片的定义

        - 图像质量：清晰度、噪声、伪影

        - 图文对齐：生成图像是否能很好反应prompt

        - 美学质量：艺术性、视觉吸引力，构图合理

        - 多样性：生成结果的丰富程度

        - 安全性：有害内容检测



#### Prompt 如何确定

一张图片可以有任意种描述方法，需要基于业务确定标准化的 prompt 格式：

- 覆盖维度：人物、景别、构图、动作、文字字体、文字颜色等

- <strong>关键原则：</strong>图片描述是否容易获得且稳定、保证训练和推理分布一致



#### 数据清洗（Data Cleaning）

<strong>一个好的模型效果，数据占到了 80%。</strong>数据清洗的核心方法：

- <strong>去重：</strong>MD5 去重 \+ 图片内容去重

- <strong>图文相关性：CLIP</strong>（对比语言\-图像预训练模型）评分过滤

- <strong>图片美学评估：</strong>人评 \+ <strong>LAION\-Aesthetics</strong>（大规模美学评分数据集）自动评分

- <strong>图片清晰度：Laplace 算子</strong>（边缘检测滤波器）检测模糊图片

- <strong>水印检测：</strong>水印检测模型过滤带水印图片

- 过滤掉不希望模型生成的图片类型



#### 反馈迭代

小批量训练 → 根据 benchmark 的反馈 → 收集相关数据补充训练 → 循环迭代



### 2\.2 后训练 / 对齐（Post\-training / Alignment）— 让模型画出想要的图

预训练让模型学会画画，后训练让模型画出符合人类偏好的图片。



#### SFT（Supervised Fine\-Tuning，监督微调）

<strong>一句话理解：</strong>用精选的高质量数据对模型进行微调。根据业务需求制备符合要求的数据，类比 LLM 的 SFT 阶段。



#### RL（Reinforcement Learning，强化学习）目前摸着 LLM 过河。

<strong>一句话理解：</strong>让模型通过「试错 \+ 反馈」学习。提高「好」图生成的概率，降低不符合预期图片生成的概率。

主要方法：

- <strong>DPO（Direct Preference Optimization，直接偏好优化）</strong>：用「好图 vs 差图」的配对数据训练，让模型学会分辨什么是好图

- <strong>GRPO（Group Relative Policy Optimization，组相对策略优化）</strong>：让模型同时生成多张图，根据评分奖优罚劣。效果更稳定但多样性会降低



## 三、推理优化（Inference Optimization）

训练好的模型在实际使用时，需要各种优化手段来降低延迟和成本。



### 3\.1 Schedule（调度器）— 去噪导航方案

<strong>Schedule（调度器）</strong>：DDPM 的去噪过程本质是偏微分方程 <strong>SDE（Stochastic Differential Equation，随机微分方程）</strong> / <strong>ODE（Ordinary Differential Equation，常微分方程）</strong> 的求解，可以用数学方法加速。

<strong>一句话理解：</strong>Schedule 就像高速公路的导航方案——同样从 A 到 B，走高速比走省道快。好的 Schedule 能用更少步数达到相同质量。

实际使用中，30\-50 步迭代通常已经足够。Schedule 的选择影响生成质量和速度的 trade\-off——类比 LLM 的 CoT 长度，更多步数不一定更好，关键是找到有效的步数范围。



### 3\.2 Flash Attention — GPU 加速

<strong>Flash Attention</strong>：解决 attention 计算的内存瓶颈。

<strong>背景：</strong>标准 softmax attention 需要计算完整的 N×N 注意力矩阵。GPU 的高速缓存 <strong>SRAM（Static RAM，静态随机存储）</strong>容量小但极快，主内存 <strong>HBM（High Bandwidth Memory，高带宽内存）</strong>容量大但相对慢。完整矩阵装不进 SRAM，必须频繁读写 HBM，成为性能瓶颈（memory\-bound）。

<strong>Flash Attention 做法：</strong>分块计算 softmax，每次只把一小块数据加载到 SRAM，增量更新注意力输出，避免大矩阵写回 HBM。

<strong>效果：</strong>attention 从 memory\-bound 变成 compute\-bound，在 A100 上速度提升 2\-4x，显存占用大幅降低。



### 3\.3 蒸馏（Distillation）— 降低推理成本

#### CFG 蒸馏

标准 CFG 推理时需要同时跑「有条件」和「无条件」两次去噪，算力翻倍。CFG 蒸馏让模型直接学会如何基于条件生成图片，<strong>节省一半算力成本</strong>。



#### 步数蒸馏

30\-50 步的迭代步数仍然很多。通过训练模型，进一步压缩迭代步数到 <strong>4\-8 步</strong>，大幅提升推理速度。



### 3\.4 并行推理与量化

#### 并行推理

同样的任务分给多个 GPU 同时处理，直接用硬件换时间。



#### 量化（Quantization）— 用精度换速度

<strong>量化（Quantization）</strong>：降低计算的数值精度，换取更快的速度和更低的显存占用。

<strong>一句话理解：</strong>就像把高清照片存为 JPG——文件小了，肉眼看几乎一样，但放大会有损失。量化程度越高，「JPG 压缩率」越高。

- <strong>FP32</strong>：全精度，可计算到小数点后 7 位

- <strong>FP16 / BF16</strong>：半精度浮点，显存减半，速度提升 1\.5\-2x，小数点后 3 位

- <strong>INT8</strong>：整数量化，显存再减半，速度再提升，轻微质量损失

- <strong>INT4</strong>：激进量化，对大模型效果明显，适合显存非常有限的场景



## 四、发展历程与里程碑：Scaling Law 的视觉实践

<strong>Scaling Law（缩放定律）</strong>：和 LLM 类似，图像生成模型的质量也随算力、参数量、数据量的增加而稳步提升。下面是关键里程碑：



### 4\.1 Stable Diffusion 系列（2021\-2023）— 开源先驱\[3\-4\]

第一个基于 Diffusion 的图像大模型。相比之前的 <strong>GAN（Generative Adversarial Network，生成对抗网络）</strong>，全面实践了 scale up：

- 使用了 Diffusion 架构，生成一张图片需要的算力提升 50x\+

- 使用了 Billion 级别的图文对数据 Laion开源数据 5B

- 但因为是 U\-Net 结构不是DIT，参数量 scale 失效，模型参数量停留在几百 M \~ 几 B



<strong>SD3 的教训：</strong>因未包含 <strong>NSFW（Not Safe/Suitable For Work，不适合工作场所的内容）</strong>训练数据，人物肢体生成严重退化——说明数据分布对模型能力边界有决定性影响，缺失的分布不是靠算力能补回来的。

[![image\.png](/images/image-generation-models/image-16.png)](/images/image-generation-models/image-16.png)



### 4\.2 Midjourney（2022）— 美学标杆

影响力最大的商业生图模型。核心优势不在模型架构，而在<strong>大规模筛选审美高分图片</strong>，把模型的美观度拉到了另一个层次，数据质量的scale

模型闭源，模型结构无法准确得知，但按照当时的进展来看，在模型方面没有什么独特优势。



### 4\.3 FLUX（2024）— 开源 DIT 标杆\[5\]

目前社区影响力较大的开源模型。关键突破：

- 引入 Transformer 架构（DIT），参数量达到 <strong>10B 量级</strong>，人体生成基本可用

- 开源后带动整个社区爆发

<strong>不足：</strong>文字生成仍不稳定，对复杂 prompt 的理解仍有不足（本质是 Text Encoder 不够强）



### 4\.4 Nano Banana（2025）— 全面 Scale Up

基本可商用的生图模型，将图片编辑任务统一。

- 参数量 scale：<strong>100B 量级 MOE DIT</strong> \+ <strong>Gemini 级别 LLM</strong> 作为 Text Encoder——大脑（理解）和手（生成）同时得到了史诗级增强

- 数据量 scale：大量精心挑选的高质量私有数据



为什么是Nnao Banana/Google？

- 从文生图扩展到图像编辑，对生成内容有更精细的控制力和对齐能力，有更丰富的落地场景

- 参数量scale： 用了100B量级的MOE DIT和 gemini级别的LLM做 text encoder部分，大脑和手都得到了史诗级加强

- 数据量的scale：用了大量精心挑选的数据，别人的老师是幼教，Nano 已经开始跟毕加索学画画

- Google 的私有数据 \+ 算力资源允许做业界最贵的尝试，其他公司难以直接复制

## 五、自研模型

### 5\.1 目标

<strong>成本显著低于 Nano Banana 的情况下，达到 Nano 80%\+ 的效果。</strong>

效果好：

- 生成图的形象和参考图形象一致

- 文字清晰正确

- 画风统一和 Nano 对齐

- 人物表现力强，有美感

- 能正确理解 Story Writer（SW）输出

成本低：

- 迭代步数更少

- 占用的 GPU 显存更少。



### 5\.2 方法：Benchmark（方向盘）\+ Scale 三要素（发动机）

在算力、参数、数据的质量和数量维度进行 scale up。



#### 模型选择

选用 `Qwen-Image-Edit 20B`，当时开源模型里参数量最大。Scale 维度：参数量。

#### Flow matching\[6\]：

- DDPM 的问题：加噪/去噪的路径是随机的，分布迁移路径复杂，单步预测难度高。

- Flow Matching思路：两点之间直线最短（最优传输路径）

<span aria-label="x_t=(1−t)x_0+te"><i>x</i><sub>t</sub> = (1−<i>t</i>)<i>x</i><sub>0</sub> + <i>t</i><i>e</i></span>

- scale：算力的利用率

[![image\.png](/images/image-generation-models/image-22.png)](/images/image-generation-models/image-22.png)

#### Prompt 格式标准化

<strong>解决的问题：</strong>模型「理解」用户意图的能力不稳定——同一张图片，不同的描述方式会产生截然不同的生成结果。

<strong>方案：</strong>基于 SW 的输出，对 Nano 生成的图片用 LLM 进行扩写，包含：人物、景别、格子数量和样式、文字位置/格式、人物外貌/动作、背景等。

确定好 prompt 格式后，用 Nano 已生成的图片 1 → LLM 生成 prompt → Nano 生成图片 2 → 对比 1 和 2 是否对齐 → 验证 prompt 的完整性。

如何优化：基于先验确定 prompt，根据 benchmark 后验持续迭代优化。

需要单独训练一个 LLM 把 SW 的输出转化为上述格式 — <strong>Prompt Enhancer</strong>。



#### 数据清洗

<strong>一个好的模型效果，数据占到了 80%。</strong>

- 基于线上的 query，用 Nano Pro 数据当 GT（Ground Truth，基准真值）

- <strong>base 数据：</strong>使用大模型过滤掉不符合要求的数据（参考图不一致、文字错误、肢体错误、不符合物理规律），保证下限

- <strong>refine 数据：</strong>通过大模型筛选出线上构图精美、表现力丰富的图片，作为 refine 数据集，提高上限



#### Benchmark 制备

- 确定不同类型 case 占比

- 根据确定的占比拉取不同难度、不同类型的线上 case 组成 benchmark

评测标准：

- 生成图片和参考图人物一致性

- 图片文字是否正确

- 图片人物肢体是否正常，是否符合物理规律

- 图片是否美观，人物是否有表现力



## 六、关键问题与解决方案

### 6\.1 文字生成问题

Diffusion 更容易学习低频信息（大色块、轮廓），高频信息（文字笔画、细节）学习困难。

<strong>解决方案：</strong>提高生成分辨率，字体更大，高频信息向低频信息过渡——本质是用更多算力换清晰度。

*人话：字更大，模型看的更清楚。Scale 维度：生成同一张图，使用了更多的算力。*

[![image\.png](/images/image-generation-models/image-20.png)](/images/image-generation-models/image-20.png)



以下是优化前后的文字生成对比：

|[![image\.png](/images/image-generation-models/image-26.png)](/images/image-generation-models/image-26.png)|[![image\.png](/images/image-generation-models/image-04.png)](/images/image-generation-models/image-04.png)|
|---|---|
|[![image\.png](/images/image-generation-models/image-25.png)](/images/image-generation-models/image-25.png)|[![image\.png](/images/image-generation-models/image-14.png)](/images/image-generation-models/image-14.png)|

### 6\.2 画风问题

Diffusion 训练使用 <strong>L2 Loss（均方误差）</strong>，本质是求平均。长难 case 会被大量简单 case 平滑掉，同一张图的复杂部分会被简单部分平滑掉。

<strong>解决方案：</strong>针对不好的画风，单独拉出来做 continue\-training（持续训练）。

*人话：哪里不会点哪里。Scale 维度：提高数据质量。*



以下是画风优化前后的对比：

|[![image\.png](/images/image-generation-models/image-01.png)](/images/image-generation-models/image-01.png)|[![image\.png](/images/image-generation-models/image-23.png)](/images/image-generation-models/image-23.png)|
|---|---|
|[![image\.png](/images/image-generation-models/image-18.png)](/images/image-generation-models/image-18.png)|[![image\.png](/images/image-generation-models/image-00.png)](/images/image-generation-models/image-00.png)|

### 6\.3 图片质量不稳定

因为噪声的随机性，图片生成具有多样性/不稳定性——同样的 prompt 每次生成结果不同。

<strong>解决方案：GRPO</strong>——模型多次采样，提高符合要求的图片生成概率，降低不符合要求的图片生成概率。结果更稳定，但多样性降低。

[![image\.png](/images/image-generation-models/image-15.png)](/images/image-generation-models/image-15.png)

## 七、待解决问题与未来方向

### 7\.1 当前待解决

- 和nano2还是有较大差距



#### 更精美的画风/更艺术的表达

- Scale 方向：数据——大量爬去nano的"好"图片，去学习

- Scale方向：模型参数量\-\-用更大的模型去学习nano

- RL 训练进一步优化



#### 二次元 / IP

- Scale 方向：数据——爬取大量高质量 IP/二次元图片，让模型学会知名 IP 和有代表性的二次元画风

- 增加搜索机制，保证对热点 IP 的跟踪能力



#### 更多画风

- 通过运营/产品了解潜在画风，提前搜集数据训练学习

- 爬取网上知名/流行艺术类图片，增加模型先验知识储备

- 更加精细的图片细节，更有感染力的画面表达

- 筛选高质量数据进行训练



#### 成本优化

- <strong>ArcFlow：</strong>迭代步数从 50 → 8

- <strong>Causal Attention：</strong>提高 attention 的效率



### 7\.2 未来技术趋势

#### MeanFlow — 一步去噪\[7\]

<strong>MeanFlow</strong>：Flow Matching 的进一步优化——理论上只需 <strong>1 步</strong>即可完成去噪，生成速度大幅提升。核心思路是直接预测期望的流速场，而不是逐步迭代。目前仍在研究阶段，但方向清晰。



#### Autoregressive Image Generation — 脑手合一\[8\]

<strong>自回归图像生成</strong>：把图像生成统一到 LLM 的自回归框架里——LLM 同时生成文字和图片，去掉独立的 Text Encoder，文字理解和图像生成合并为同一个模型。

- <strong>优势：</strong>脑手合一，理解能力更强；一套模型解决多模态生成

- <strong>挑战：</strong>图像 token 序列长；需要高质量的图文交错训练数据



#### 图片版 CoT — 先画草稿再精修\[9\]

类比 LLM 的 Chain\-of\-Thought：先生成低质量草稿，再基于草稿精化生成完整高质量图片。



#### 生图 Agent 化 — 从「生成一张图」到「完成一个创作任务」

- 生图 Agent 化的愿景：context \+ 知识搜索 → 草稿生成 → react 反思迭代 → 最终输出

- Agent（智能体）= LLM（模型）\+ Harness（完整控制系统）。\[10\]

- LangChain 团队实验：相同模型，不同 Harness，Agent 的成功率从 52\.8% 提升到 66\.5%。\[11\]

<strong>Harness（脚手架/控制系统）</strong>是什么？以 Claude Code 举例：

- <strong>消息注入队列：</strong>在对话流中注入环境信息、权限变更、上下文更新——这些用户看不到

- <strong>Prompt 组装引擎：</strong>每次调用 LLM 都是动态 prompt，会根据任务阶段、可用工具、历史错误等动态调整

- <strong>Skills 维护：</strong>动态选择需要调用的工具

- <strong>安全系统：</strong>各种文件隔离、权限控制等

- <strong>上下文工程：</strong>memory 的压缩和生成

- <strong>每步撤销：</strong>对于文件的修改可以随时撤销









#### 更远的未来

图片 → 视频 → 世界模型：模态的终极统一



## 八、相关资料

### 8\.1 AIGC 社区

- [Civitai](https://civitai.com/models) — 全球最大的 AIGC 社区之一



### 8\.2 视频（推荐入门）

- <strong>3Blue1Brown \- But what is a neural network?</strong>：神经网络直觉入门，动画极好 → [YouTube](https://www.youtube.com/watch?v=aircAruvnKk)

- <strong>Andrej Karpathy \- Let's build GPT</strong>：从零实现一个 LLM，理解 Transformer 最好的资料 → [YouTube](https://www.youtube.com/watch?v=kCc8FmEb1nY)

- <strong>Computerphile \- Stable Diffusion</strong>：Stable Diffusion 原理通俗讲解 → [YouTube](https://www.youtube.com/watch?v=1CIpzeNxIhU)

- <strong>李沐 \- Diffusion 论文精读</strong>：中文，逐步讲解 DDPM 论文 → [YouTube](https://www.youtube.com/watch?v=fbLgFrlTnGU)



### 8\.3 文章（进阶）

- <strong>苏剑林的科学空间</strong>（数学方法解释深度学习）：[spaces\.ac\.cn](https://spaces.ac.cn/)

- <strong>Lilian Weng \- What are Diffusion Models?</strong>（英文最系统的综述之一）：[lilianweng\.github\.io](https://lilianweng.github.io/posts/2021-07-11-diffusion-models/)

- <strong>Jay Alammar 可视化教程</strong>（Transformer、BERT 等可视化讲解，直觉极强）：[jalammar\.github\.io](https://jalammar.github.io)



### 8\.4 参考文献

- \[1\] DDPM：[arxiv\.org/abs/2006\.11239](https://arxiv.org/abs/2006.11239)

- \[2\] CFG：[arxiv\.org/abs/2207\.12598](https://arxiv.org/abs/2207.12598)

- \[3\] Stable Diffusion XL：[arxiv\.org/abs/2307\.01952](https://arxiv.org/abs/2307.01952)

- \[4\] Stable Diffusion \(LDM\)：[arxiv\.org/abs/2112\.10752](https://arxiv.org/abs/2112.10752)

- \[5\] FLUX：[github\.com/black\-forest\-labs/flux](https://github.com/black-forest-labs/flux)

- \[6\] Flow Matching：[arxiv\.org/abs/2210\.02747](https://arxiv.org/abs/2210.02747)

- \[7\] MeanFlow：[arxiv\.org/abs/2505\.13447](https://arxiv.org/abs/2505.13447)

- \[8\] Autoregressive Image Generation：[arxiv\.org/pdf/2509\.23951](https://arxiv.org/pdf/2509.23951)

- \[9\] 图片版 CoT：[arxiv\.org/abs/2505\.22525](https://arxiv.org/abs/2505.22525)

- \[10\] Harness Engineering \(OpenAI\)：[openai\.com](https://openai.com/zh-Hans-CN/index/harness-engineering/)

- \[11\] Improving Deep Agents with Harness Engineering \(LangChain\)：[blog\.langchain\.com](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/)
