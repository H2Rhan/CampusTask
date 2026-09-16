# 系统架构设计 —— CampusTask · 邻行

> 版本：v0.1 · 2026-09-16

## 1. 总体架构

```
                 微信小程序（原生 + TypeScript）
                     │  REST / WebSocket
                     ▼
                 Nginx（反向代理 / WS Upgrade）
                     │
              FastAPI 应用层（API v1）
   ┌─────────┬───────┴────┬──────────┬───────────┐
   ▼         ▼            ▼          ▼           ▼
 用户服务   任务服务     匹配引擎   钱包服务     仲裁服务
   │         │            │          │           │
   │         │       ┌────┴────┐     │           │
   │         │       ▼         ▼     │           │
   │         │    校园地图   AI 解析  │           │
   │         │    (图算法)  (LLM+规则)│           │
   ▼         ▼            │          ▼           ▼
        MySQL（用户/任务/钱包/聊天/仲裁/信用/评价）
                     │
                   Redis（在线状态 / 缓存，可选）
```

华为 ICT 演进方向：LLM 推理迁移至 **昇腾 / ModelArts**，部署至 **华为云 ECS + RDS**，
小程序形态可扩展 **鸿蒙原生应用**（对应 C4-AI 鸿蒙高校创新赛赛道）。

## 2. 后端分层

```
server/app/
├── core/            # 配置（pydantic-settings）、安全（PBKDF2+JWT）、依赖注入
├── db/              # SQLAlchemy 2.0 engine/session/Base
├── models/          # User/UserRoute/Task/TaskEvent/Wallet/Tx/Chat/Arbitration/Review
├── schemas.py       # Pydantic v2 输入输出契约
├── campus_map/      # 校园图（graph.py）+ 路径算法（routing.py）+ 图数据（data/jinnan.json）
├── ai/              # 自然语言任务解析（LLM 引擎 + 规则引擎兜底）
├── services/        # 业务核心：
│   ├── state_machine.py      # 任务状态机（唯一合法迁移入口）
│   ├── task_service.py       # 任务生命周期（创建/接单/推进/验收/取消）
│   ├── matching_service.py   # 边际成本匹配引擎（核心算法）
│   ├── wallet_service.py     # 冻结/解冻/结算/服务费
│   ├── credit_service.py     # 信用分规则
│   └── arbitration_service.py# 证据时间线 + 规则引擎建议 + 裁决执行
└── api/v1/          # auth/users/tasks/map/match/ai/wallet/arbitration/chat(WS)
```

设计原则：

- **状态机唯一入口**：任何状态变更必须经过 `state_machine.assert_transition`，非法迁移在服务端直接 400
- **资金与状态同事务**：冻结/结算与任务状态变更在同一 DB 事务内提交，失败整体回滚
- **事件溯源**：所有关键动作写入 `task_events`，仲裁时间线与审计直接复用

## 3. 核心算法

### 3.1 最短路径

- Dijkstra（精确解，默认）与 A*（欧氏启发式，演示对比）双实现，结果一致性由测试保证

### 3.2 边际成本匹配（创新点 2）

```
输入：任务 T(pickup, dropoff)，候选用户 U 的日常路线 plan = [n₁, n₂, ..., nₖ]
1. original = Σ shortest(nᵢ → nᵢ₊₁)
2. 枚举插入位置 (i, j), i ≤ j：candidate = plan[:i] + [pickup] + plan[i:j] + [dropoff] + plan[j:]
   with_cost = min Cost(candidate)     # Best Insertion，保证先取后送
3. MC = with_cost − original            # 边际出行成本
4. Score = w₁(1−MC_d/D₀) + w₂(1−MC_t/T₀) + w₃·credit/120 + w₄·reward/R₀
   match_percent = Score × 100
```

复杂度：O(k² · Dijkstra)，k ≤ 10 的校园场景下毫秒级；多任务批量分配可扩展为
带容量约束的车辆路径问题（CVRP）——即数维杯数学建模作品的切入点。

### 3.3 AI 任务解析（创新点 3）

- **LLM 引擎**：OpenAI 兼容 chat/completions，零温度，JSON 严格输出，地点再经校园图别名映射归一化
- **规则引擎兜底**：地点提及位置 + 方位动词（从/去/到/送）判定起终点；中文数字时间（下午五点/十二点半）；
  金额正则（块/元/¥）；类型关键词优先级匹配。无 API Key 时全自动降级，保证 Demo 永不翻车

## 4. 数据模型（主要表）

| 表 | 说明 | 关键字段 |
|---|---|---|
| users | 用户与信用 | student_no, credit_score, tasks_completed, good_reviews |
| user_routes | 日常路线（匹配输入） | waypoints(JSON) |
| tasks | 任务 | publisher/accepter, start/end_node, reward, status, distance |
| task_events | 任务事件溯源 | event, detail, actor_id |
| wallets / wallet_transactions | 钱包与流水 | balance, frozen / kind, amount |
| chat_messages | 聊天（含系统消息） | task_id, msg_type |
| arbitrations | 仲裁 | evidence(JSON), verdict, suggestion |
| reviews | 互评 | rating 1–5 |

## 5. 安全与合规

- 密码：PBKDF2-HMAC-SHA256（12 万次迭代，随机盐）
- 鉴权：JWT（HS256），WebSocket 经 query token 鉴权
- 权限：接口级角色校验（发布者 / 接单者 / 双方 / 管理员）
- 支付合规：Demo 虚拟钱包；正式环境对接持牌支付机构，平台不沉淀资金

## 6. 部署

- 开发：`uvicorn app.main:app --reload`（SQLite 零依赖）
- 生产：Docker Compose（app + MySQL 8.4 + Redis 7 + Nginx），Nginx 处理 WS Upgrade
- 种子数据：`python -m scripts.seed`（4 个演示账号 + 日常路线）
