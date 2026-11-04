---
title: "浅谈容器二三事 1.0"
description: '一次部署背后的 "Tiki-Taka"：构建、部署、服务发现与健康检查。'
date: 2026-07-30
tags: [Kubernetes]
draft: false
---

## I 站在光里: 一次部署背后的 "Tiki\-Taka"

### 从流水线到k8s

<figure class="payment-diagram">
  <div class="diagram-scroll"><a href="/images/container-notes/delivery-pipeline.png"><img src="/images/container-notes/delivery-pipeline.png" width="1536" height="1024" loading="lazy" decoding="async" alt="从代码、Git 仓库与 CI 构建，到镜像仓库、部署 YAML 和 Kubernetes 集群的完整链路" /></a></div>
</figure>

|**概念**|**一句话解释**|
|---|---|
|**CI**|自动把代码编译、测试、打包|
|**镜像（Image）**|已经打包好的应用，可以复制到任何机器运行|
|**镜像仓库（ACR）**|存放所有镜像的地方|
|**YAML**|描述"我希望系统变成什么样"的说明书|
|**kubectl**|和 Kubernetes 交流的入口|
|**API Server**|Kubernetes 唯一的大门，所有请求都必须经过这里|
|**Deployment**|描述应用应该运行多少个、副本如何升级|
|**Pod**|Kubernetes 中真正运行程序的最小单位|
|**Container（容器）**|真正运行你的程序。|
|**Node**|提供 CPU、内存的物理机|
|**Scheduler**|决定 Pod 应该放到哪台机器|
|**kubelet**|每台机器上的执行者，负责把 Pod 真正启动起来|
|**Container Runtime**|真正负责启动容器|
|**Service**|给 Pod 一个稳定入口，不管 Pod 怎么变化都能访问|
|**Ingress**|把外部流量引进 Kubernetes|

### 阶段一 · 构建：代码 → 镜像

> **Dockerfile —— 决定"构建出什么镜像"**
>
>

<https://codeup.aliyun.com/dnyx/backend/hello-world-service/blob/master/Dockerfile>

```dockerfile
# ---- 构建阶段 ----
FROM dnyx-registry-vpc.cn-shanghai.cr.aliyuncs.com/infra/golang:1.24.0 AS builder
WORKDIR /src
COPY go.mod go.sum ./          # 先拷依赖清单，利用层缓存
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app/svc ./...

# ---- 运行阶段 ----
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /app/svc /app/svc
USER dnyx
EXPOSE 8080
ENTRYPOINT ["/app/svc"]

```

**官方链接**：[Docker 多阶段构建](https://docs.docker.com/build/building/multi-stage/) ｜ [Docker 构建最佳实践](https://docs.docker.com/build/building/best-practices/)

#### 为啥构建/发布突然超时了: ACR 与 VPC 域名

**配置**：ACR 三层结构 **实例 → 命名空间 → 仓库**。本例 `dnyx-registry.cn-shanghai.cr.aliyuncs.com` 是**企业版**格式，实例 `dnyx`、命名空间 `infra`、仓库 `helloworld`。

**\*\-vpc 内网域名 vs 公网域名（为什么构建时 FROM \.\.\.\-vpc\.\.\.）**：

VPC 内网域名 `dnyx-registry-vpc...` 只在同地域 VPC 内可达，推拉走内网、不耗公网流量、延迟低带宽高。构建在同地域 VPC 内的构建机上，用 `-vpc` 拉基础镜像又快又免流量费。**规则：登录域名与推拉域名必须一致**。本地开发机不在 VPC 内、无法解析 `-vpc`才用公网域名。

#### 回滚的基石: IMAGE\_TAG

- 找茬，下面这段流水线的配置会导致什么问题

<figure class="payment-diagram">
  <div class="diagram-scroll"><a href="/images/container-notes/pipeline-tag.png"><img src="/images/container-notes/pipeline-tag.png" width="2860" height="1740" loading="lazy" decoding="async" alt="原文流水线配置截图：镜像标签设置为 latest，使用 VPC 地址推送镜像" /></a></div>
</figure>

**配置**：镜像 tag（本例 `${IMAGE_TAG}`）决定"部署的是哪一版代码"以及"能不能可靠回滚"。核心原则：**tag 唯一、不可变、可追溯**——推荐 commit SHA 或时间戳，**禁止 latest**。

```bash
IMAGE_TAG=$(git rev-parse --short HEAD)   # 如 3b02b32
docker build -t dnyx-registry-vpc.cn-shanghai.cr.aliyuncs.com/infra/helloworld:${IMAGE_TAG} .
docker push dnyx-registry-vpc.cn-shanghai.cr.aliyuncs.com/infra/helloworld:${IMAGE_TAG}

```

**最佳实践**：禁用 `latest`（会被覆盖导致"同 tag 不同内容"，且 k8s 对 latest 默认 `imagePullPolicy: Always`）；tag 绑定 commit SHA；回滚即换 tag（每版不可变且都在 ACR 保留）；配 `imagePullPolicy: IfNotPresent`。

**官方链接**：[个人版与企业版差异](https://help.aliyun.com/zh/acr/product-overview/differences-between-personal-edition-instances-and-enterprise-edition-instances) ｜ [基于 Docker 的基本操作](https://help.aliyun.com/zh/acr/getting-started/basic-operations-on-docker)

启发：镜像 = 代码 \+ 运行环境的**不可变快照**。正因不可变，"同一包跑遍各环境、回滚=换回旧 tag"才成立。

---

### 阶段二 · 部署：yaml → Container

> **deployment/k8s\-deployment\.yaml —— 决定"k8s 怎么跑它"**
>
>

<https://codeup.aliyun.com/dnyx/backend/hello-world-service/blob/master/deployment/k8s-deployment.yaml>

```yaml
# k8s deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-world-service${SWIM_LANE_POSTFIX}
  namespace: default
spec:
  replicas: ${USER_REPLICAS_SNAPSHOT}
  selector:
    matchLabels:
      app: hello-world-service
  strategy:
    rollingUpdate:
      maxSurge: 100%
      maxUnavailable: 0
    type: RollingUpdate
  template:
    metadata:
      labels:
        app: hello-world-service
        is: hello-world-service
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - hello-world-service
                topologyKey: kubernetes.io/hostname
              weight: 100
      containers:
        - name: hello-world-service
          image: dnyx-registry.cn-shanghai.cr.aliyuncs.com/infra/helloworld:${IMAGE_TAG}
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
              scheme: HTTP
            initialDelaySeconds: 30
            periodSeconds: 3
            successThreshold: 1
            timeoutSeconds: 3
            failureThreshold: 3
          livenessProbe:
             failureThreshold: 5
             initialDelaySeconds: 60
             periodSeconds: 10
             successThreshold: 1
             tcpSocket:
               port: 8080
             timeoutSeconds: 3
          env:
            - name: ENV
              value: ${ENV}
            - name: SWIM_LANE
              value: ${SWIM_LANE}
            - name: aliyun_logs_${ENV}-application
              value: stdout
            - name: aliyun_logs_${ENV}-application_project
              value: dnyx-microservice
            - name: aliyun_logs_${ENV}-application_ttl
              value: '15'
            - name: aliyun_logs_${ENV}-application_shard
              value: '2'
          resources:
            requests:
              memory: '128Mi'
              cpu: '0.1'
            limits:
              memory: '128Mi'
              cpu: '0.1'
          lifecycle:
            preStop:
              exec:
                command: [ "sh", "-c", "sleep 30" ]
          securityContext:
            allowPrivilegeEscalation: false
            privileged: false
      imagePullSecrets:
        - name: ali-registry

# k8s service
---
apiVersion: v1
kind: Service
metadata:
  name: hello-world-service
  namespace: default
  labels:
    app: hello-world-service
spec:
  ports:
    - name: http
      port: 80
      targetPort: 8080
  selector:
    app: hello-world-service

```

#### 从“力工思维”的理解 Service → Deployment → Pod → Container

<figure class="payment-diagram">
  <div class="diagram-scroll"><a href="/images/container-notes/cluster-overview.png"><img src="/images/container-notes/cluster-overview.png" width="1536" height="1024" loading="lazy" decoding="async" alt="Kubernetes 控制平面和工作节点的组件及数据流关系" /></a></div>
</figure>



<figure class="payment-diagram">
  <div class="diagram-scroll"><a href="/images/container-notes/service-deployment-pod.png"><img src="/images/container-notes/service-deployment-pod.png" width="1536" height="1024" loading="lazy" decoding="async" alt="原文以图说明 Service、Deployment、Pod 与 Container 的职责和关系" /></a></div>
</figure>

#### Nobody → Somebody: Deployment vs StatefulSet

> Stateless means interchangeable\. Stateful means identifiable\.
>
>

|**维度**|**无状态 Stateless**|**有状态 Stateful**|
|---|---|---|
|请求|任意副本都能处理任意请求|请求绑定特定实例|
|本地数据|不依赖本地持久数据，state 外置到 DB/Redis/OSS|有跟随实例的持久数据|
|实例身份|无身份，副本完全等价、可互换|有身份/序号，可能有主从、有顺序|
|增删副本|随意，克隆即可|谨慎，涉及数据迁移/选主|
|k8s 原语|Deployment / ReplicaSet|StatefulSet（\+PVC\+Headless Service）|
|例子|Web 服务|ZooKeeper|

Deployment 本身并不会创建 Pod，它更像一个"需求单"。当 YAML 提交到 API Server 后，Kubernetes 后台会有一个 Deployment Controller 持续监听变化，并根据 YAML 自动创建或删除 Pod；Scheduler 为新 Pod 挑选运行节点，Node 上的 kubelet 再调用容器运行时（containerd）启动容器。整个过程不断循环，直到实际运行状态与 YAML 描述完全一致。

开放讨论：

- 我们工程中的 MySQL / Redis 是部署在 Deployment 中还是 StatefulSet 中？

- star\-service 中创作链路，其实很像 Stateful

**官方链接：**[StatefulSet Basics](https://kubernetes.io/docs/tutorials/stateful-application/basic-stateful-set/?utm_source=chatgpt.com) \| [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)

#### 一个密钥是怎么注入的

Secret 是 Kubernetes 的密钥管理机制，敏感信息统一存储于集群中。Pod 启动时，kubelet 根据声明自动将 Secret 以环境变量的形式注入容器，实现密钥与应用代码、镜像彻底解耦。

```yaml
containers:
        - name: star-service${SWIM_LANE_POSTFIX}
          image: dnyx-registry.cn-shanghai.cr.aliyuncs.com/infra/star-service:${IMAGE_TAG}
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
            - containerPort: 9000
              name: metrics
          env:
            # MySQL 敏感信息从secret获取
            - name: STAR_MYSQL_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: star-mysql
                  key: password
```

- 集群里面应该配置什么，最后由会映射成什么？

**官方链接**：[ACK 在 Pod 中使用配置项](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/configure-a-pod-to-use-a-configmap) ｜ [ACK 使用保密字典](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/configure-a-pod-to-use-a-secret)

#### Service 与服务发现

- 一个反直觉的点：Client → Service → Pod ❌，Service 从来不会转发任何一个数据包，真正转发流量的是？

- Service 只是定义了一条规则："这个 VIP 后面有哪些 Pod。"

##### 进门：外部流量如何进入 Kubernetes

互联网用户访问的是：

```text
https://api.example.com
```

首先发生的不是 Kubernetes，而是公网 DNS：

```text
api.example.com
        │
        ▼
公网 DNS
        │
        ▼
SLB 公网 IP
```

随后，请求到达阿里云 SLB。

SLB 的后端挂着 Kubernetes 集群的一组 Node，它根据负载均衡算法（轮询、最小连接数等）挑选一个节点，把流量送进去。

这里完成了**第一次负载均衡：选 Node。**

> **SLB 负责回答："请求应该进入哪台 Kubernetes 节点？"**
>
>

##### 找服务：Ingress Controller 如何决定去哪个 Service

请求进入集群后，到达的是 Ingress Controller（例如 NGINX Ingress）。

Ingress Controller 根据 Ingress 规则查看：

```yaml
rules:
- host: api.example.com
  http:
    paths:
    - path: /order
      backend:
        service:
          name: order-service
          port:
            number: 80
```

也就是说：

Ingress Controller 完成的是：Host \+ Path → Service

它决定：

> **这个请求应该交给哪个 Kubernetes Service。**
>
>

注意：

它还没有找到 Pod。

##### 找入口：CoreDNS 如何找到 Service 的 VIP

确定 Service 之后，还需要知道：

```text
order-service
```

到底在哪。

这时：

CoreDNS 登场。

它负责维护：Service Name → ClusterIP\(VIP\)

例如：

```text
order-service.default.svc.cluster.local

↓

10.96.0.18
```

于是：

请求真正访问的是：

```text
10.96.0.18
```

也就是：

Service 的虚拟 IP（ClusterIP）。

##### 落地即分发:节点上 kube\-proxy 的规则表

包一落到这个节点,内核里早就写好的转发规则立刻接管:

- 规则里存着一张表:Service 的 VIP\(虚拟 IP\)→ 这个服务所有健康 Pod 的 IP 列表

- 内核照这张表,把包的目的地址 DNAT 改写成其中一个真实 Pod 的 IP\(随机/轮询挑一个\)

关键就一句:这张表本地就有、就在内核里,不用问任何人、当场就能转。 而且挑中的 Pod 可以在任意节点上——所以第 1 块随便从哪个节点进来都无所谓,第 2 块保证能转到正确的 Pod。

这是第二次负载均衡:选 Pod,由 kube\-proxy 写的规则 \+ 内核完成。



##### 这张表凭什么一直是新鲜的:list\-watch

Pod 会不断发布、扩缩、挂掉,kube\-proxy 手里那张 VIP→Pods 表凭什么总是最新的?

答案:它不是自己算的,是订阅apiserver 来的。这就是 list\-watch:

- list:kube\-proxy 启动时,先向 apiserver 拉一次全量\(现在有哪些 Service、每个的后端 Pod 是谁\)

- watch:然后挂一条长连接,只要后端有变化,apiserver 主动把事件推给它

- 一收到"某 Pod 上线/下线"的事件,kube\-proxy 立刻改内核规则

重点:不是 kube\-proxy 反复轮询"变了吗变了吗",是 apiserver 主动推。 全集群每个节点的 kube\-proxy 都这样订阅,所以一次变化能同步到所有节点。\(list\-watch 是 k8s 所有组件同步状态的通用机制,不只 kube\-proxy 用——记住这个词,后面处处是它。\)



##### 谁往表里写、服务名怎么解析:剩下的角色

- 表是谁填的? —— EndpointSlice 控制器,真正的"注册员"。它也 list\-watch 所有 Pod 和 Service,规则极简:谁的 label 匹配某 Service 的 selector、且 Ready,就把它的 IP 写进这个 Service 的后端表。 Pod 从不主动注册,是被这个控制器"点名"进表的。

- 集群内部互相调用怎么办? —— 用服务名\(orca 或 orca\.default\.svc\.cluster\.local\)。CoreDNS 先把名字解析成 VIP,然后就回到第 2 块的流程。CoreDNS 那张"名字→VIP"表,同样靠 list\-watch 维护。



##### 彩蛋：形而上的思考

- 如果把 kube\-proxy 杀了，访问 order\-service 的流量，还能正常运转嘛？如果控制平面挂了呢？

- 传统微服务的服务发现是怎么做的：注册中心



**官方链接**：[Kubernetes Service](https://kubernetes.io/docs/concepts/services-networking/service/) ｜ [ACK DNS 解析异常排查](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/support/dns-troubleshooting)

---

### 阶段三 · 发布：期望态 → 流量进来（k8s 自己收敛）

#### 健康检查探针 readiness / liveness / startup

|探针|探测什么|失败后动作|影响面|
|---|---|---|---|
|**readinessProbe**|是否准备好接流量|**从 Endpoints 摘除**，不重启|只影响收不收流量|
|**livenessProbe**|进程是否还活着|**kill 容器并重启**|会重启|
|**startupProbe**|是否已完成启动|未成功前挂起 liveness/readiness|保护慢启动|

- 你觉得这段探针写的如何?

```go
// health.go
  func HealthCheck(c *gin.Context) {
      // 确保order服务正常
      if resp, err := http.Get("http://order-service/health"); err != nil || resp.StatusCode != 200 {
          c.JSON(503, gin.H{"status": "order-service down"})
          return
      }
      c.JSON(200, gin.H{"status": "healthy"})
  }
```

```yaml
livenessProbe:
    httpGet: { path: /health, port: 8080 }
    initialDelaySeconds: 30
    periodSeconds: 10
    failureThreshold: 3
```

- 从工程中的探针设置能学到什么

<https://codeup.aliyun.com/dnyx/backend/star-service/blob/master/deployment/k8s-mesh-prod.yaml>

```yaml
readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            successThreshold: 1
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            successThreshold: 1
            failureThreshold: 3
```

**为什么本例 readiness 用 httpGet\(/health\)（严）、liveness 用 tcpSocket（宽）**：readiness 决定"给不给流量"，走 HTTP 到应用层反映依赖就绪，要严；liveness 决定"杀不杀了重启"，只看 TCP 端口连通，要宽。

关键反直觉点：**liveness 绝不能查外部依赖**——若 liveness 也查 DB，一旦 DB 抖动 → 所有 Pod liveness 同时失败 → 集体重启 → 重启也连不上 → CrashLoopBackOff 雪崩，把依赖抖动放大成全站宕机。

与业务的联系（伏笔 Informer 预热）：本例 `/health` 只 `c.Status(200)`，没查 DB/Redis、没看缓存热没热 → **readiness 通过 ≠ 能扛满载**，只说"我端起来了"、不说"我预热好了"。这正是后续流量预热要补的缺口。

**配错三类典型故障**：① readiness 缺失/太松 → 流量打到没就绪 Pod → 502；② liveness 太严 → 抖动被判死 → CrashLoop；③ 慢启动被杀 → **正解是加 startupProbe，而非无限调大 liveness 的 initialDelay**。

**官方链接**：[Kubernetes 配置存活/就绪/启动探针](https://kubernetes.io/zh-cn/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

## II 追随光: k8s 设计哲学

敬请期待

## III 成为光: k8s 源码精读

敬请期待

## IV 发散光: 容器世界的传道者

敬请期待
