from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = ROOT / 'plans' / 'nebularpc' / 'plan.json'
OUT_DIR = ROOT / 'plans' / 'nebularpc' / '节点执行包'
OUT_DIR.mkdir(parents=True, exist_ok=True)

DIMENSIONS = [
    ('explanation', 15),
    ('prediction', 15),
    ('implementation', 25),
    ('diagnosis', 25),
    ('transfer', 20),
]


def leaf(code, title, detail, purpose, minutes=15, done_when=None, evidence_required=False):
    return {
        'id': code,
        'title': title,
        'detail': detail,
        'purpose': purpose,
        'estimated_minutes': minutes,
        'required': True,
        'evidence_required': evidence_required,
        'evidence_fields': ['source_path', 'function_name', 'note'] if evidence_required else ['note'],
        'done_when': done_when or [f'能够明确说明：{title}', '留下可回看的简短记录'],
    }


def custom_s001(node):
    cap = node['capability']
    groups = []
    groups.append({
        'id': 'eventloop', 'title': '1. EventLoop / Reactor 审计',
        'description': '只做源码审计与能力边界确认，不重新实现 Reactor。',
        'items': [
            leaf('S0-01-EL-01','定位 EventLoop::loop() 主循环','在 MyMuduo 中找到 EventLoop 主循环实现，确认它如何进入 poll/epoll 等待。',cap,10,['记录源码文件路径','记录 EventLoop::loop() 函数位置','用一句话描述循环职责'],True),
            leaf('S0-01-EL-02','定位 Poller/EPollPoller 调用链','从 EventLoop::loop() 向下追踪到 Poller/EPollPoller 的 poll 调用。',cap,15,['画出 EventLoop → Poller/EPollPoller 调用链','绑定至少一个真实函数名'],True),
            leaf('S0-01-EL-03','确认 active Channel 分发路径','追踪 epoll 返回后 active channels 如何回到 Channel::handleEvent()/等价入口。',cap,15,['写出事件返回后的对象级分发路径','绑定源码位置'],True),
            leaf('S0-01-EL-04','确认 runInLoop / queueInLoop 语义','找到跨线程或同线程任务投递相关实现，并区分立即执行与排队执行。',cap,15,['记录 runInLoop/queueInLoop 或等价函数','说明它们与线程归属的关系'],True),
            leaf('S0-01-EL-05','确认 eventfd 唤醒路径','找到 eventfd 创建、写入、读取和唤醒 EventLoop 的完整路径。',cap,15,['绑定 eventfd 相关源码位置','写出 foreign thread → wakeup → loop 的链路'],True),
            leaf('S0-01-EL-06','写清 One Loop Per Thread 所有权','基于源码而不是 README，确认 EventLoop 与线程之间的实际约束。',cap,15,['说明一个 EventLoop 是否固定线程','指出线程检查/断言/调用边界的源码证据'],True),
            leaf('S0-01-EL-07','形成 EventLoop 审计结论','把本组结论写入 NebulaRPC/docs/history/MYMUDUO_AUDIT.md。',cap,15,['文档出现“已解决能力 / 技术债 / 可复用边界”三类结论','每条结论至少有一个源码路径或函数名'],True),
        ]
    })
    groups.append({
        'id': 'tcpconnection', 'title': '2. TcpConnection 非阻塞收发与生命周期审计',
        'description': '重点确认 partial write、output buffer、EPOLLOUT 和生命周期，而不是重写。',
        'items': [
            leaf('S0-01-TC-01','定位 TcpConnection::handleRead()','找到可读事件进入 TcpConnection 的实际处理函数。',cap,10,['记录 handleRead/等价函数位置','说明数据最终进入哪个 Buffer/回调'],True),
            leaf('S0-01-TC-02','定位发送入口 send()','找到应用层进入 TcpConnection 发送路径的入口，并记录线程切换点。',cap,10,['绑定 send/等价入口','说明调用线程与 owner loop 的关系'],True),
            leaf('S0-01-TC-03','定位 sendInLoop()/等价写函数','追踪真正执行 socket write 的函数。',cap,10,['记录函数位置','指出实际 write/send syscall 所在位置'],True),
            leaf('S0-01-TC-04','确认 partial write 后剩余 bytes 所有权','追踪第一次 write 未写完时剩余数据如何保存。',cap,20,['指出剩余 bytes 保存对象/Buffer','指出何时转入 output buffer','绑定源码位置'],True),
            leaf('S0-01-TC-05','确认何时 enable EPOLLOUT','找到写不完后打开可写事件监听的真实代码。',cap,15,['记录 enableWriting/等价调用','说明触发条件'],True),
            leaf('S0-01-TC-06','定位 handleWrite()/等价 flush 路径','追踪 EPOLLOUT 到达后如何继续发送 output buffer。',cap,15,['写出 Channel → TcpConnection writable callback 链','绑定函数位置'],True),
            leaf('S0-01-TC-07','确认何时 disable EPOLLOUT','确认 output buffer 清空后是否关闭可写事件监听。',cap,15,['指出关闭 EPOLLOUT 的条件','说明若不关闭可能发生什么'],True),
            leaf('S0-01-TC-08','定位 handleClose()/连接关闭入口','找到 FIN/RST/错误等最终进入关闭流程的主要入口。',cap,15,['绑定关闭函数','记录 channel/poller/connection 的清理顺序'],True),
            leaf('S0-01-TC-09','审计 shared_ptr / weak_ptr 生命周期','找出 TcpConnection 在回调和容器中的所有权策略，确认是否避免回调期间销毁。',cap,20,['至少找到一处 shared_ptr/weak_ptr/tie/guard 相关证据','说明对象何时允许销毁'],True),
            leaf('S0-01-TC-10','列出 TcpConnection 历史技术债','只基于真实源码列出仍不能直接带入 NebulaRPC 的边界，不做优化。',cap,15,['至少记录 1 个“需要最小恢复或重新验证”的点','不得把后续协程/RPC 问题写进来'],True),
            leaf('S0-01-TC-11','形成 TcpConnection 审计结论','把读写路径、EPOLLOUT、不变量和生命周期结论写入审计文档。',cap,20,['文档能独立回答 1MB payload 第一次只写一部分时后续如何推进','绑定对应源码位置'],True),
        ]
    })
    groups.append({
        'id': 'connector', 'title': '3. Connector 审计',
        'description': '确认连接建立、完成、失败、重试与 EventLoop 的关系。',
        'items': [
            leaf('S0-01-CO-01','定位 Connector::connect()','找到非阻塞 connect 的发起路径。',cap,10,['绑定 connect/等价函数','记录 socket 状态变化'],True),
            leaf('S0-01-CO-02','定位 connecting()/Channel 注册','找到 EINPROGRESS 后如何注册可写事件等待连接完成。',cap,15,['写出 fd → Channel → EPOLLOUT 连接完成路径'],True),
            leaf('S0-01-CO-03','确认连接成功检测','找到 SO_ERROR/getSocketError 或等价判断。',cap,10,['绑定成功/失败判断函数','说明成功后 fd 如何交给上层'],True),
            leaf('S0-01-CO-04','确认连接失败路径','追踪连接失败后的 channel 清理与状态回退。',cap,15,['绑定失败路径','记录资源是否被释放'],True),
            leaf('S0-01-CO-05','确认 retry 行为','如果实现了重试，记录触发条件和调度方式；如果没有，也要用源码证明。',cap,15,['记录 retry/定时相关入口或明确“未实现”证据'],True),
            leaf('S0-01-CO-06','形成 Connector 审计结论','写清 Connector 哪些事件驱动能力可作为 NebulaRPC 的历史基础。',cap,15,['写入审计文档','至少绑定两个函数位置'],True),
        ]
    })
    groups.append({
        'id': 'tcpclient', 'title': '4. TcpClient 审计',
        'description': '确认 TcpClient 如何把 Connector 与 TcpConnection 串起来。',
        'items': [
            leaf('S0-01-CL-01','定位 TcpClient 创建/持有 Connector','找到 TcpClient 与 Connector 的成员关系和初始化位置。',cap,10,['记录文件/成员/构造位置'],True),
            leaf('S0-01-CL-02','追踪 Connector → TcpClient 的 fd 交接','找到连接成功回调如何把 socket fd 交给 TcpClient。',cap,15,['写出回调链','绑定函数名'],True),
            leaf('S0-01-CL-03','定位 newConnection()/等价入口','确认 TcpClient 如何创建 TcpConnection 并注册回调。',cap,15,['记录创建 TcpConnection 的函数','记录 EventLoop 归属'],True),
            leaf('S0-01-CL-04','定位 removeConnection()/关闭回调','确认连接关闭后 TcpClient 如何移除或释放 connection。',cap,15,['绑定 remove/close 回调','说明所有权释放点'],True),
            leaf('S0-01-CL-05','形成 TcpClient 审计结论','写清它为什么已经比旧 ReceiverThread 客户端更接近事件驱动网络基础，但仍不等于 Async RPC。',cap,20,['只讨论当前节点网络能力边界','写入审计文档并绑定源码'],True),
        ]
    })
    groups.append({
        'id': 'buffer', 'title': '5. Buffer 审计',
        'description': '确认 Buffer 如何服务 TcpConnection 的增量读写。',
        'items': [
            leaf('S0-01-BF-01','定位 readableBytes()/可读区语义','确认 Buffer 的读索引与可读字节计算。',cap,10,['绑定函数位置','用图或文字写出 reader/writer index 关系'],True),
            leaf('S0-01-BF-02','定位 writableBytes()/可写区语义','确认可写空间与扩容/整理策略。',cap,10,['绑定函数位置','说明空间不足时怎么处理'],True),
            leaf('S0-01-BF-03','定位 append() 写入路径','确认应用数据如何追加到 Buffer。',cap,10,['绑定 append/ensureWritable 等相关函数'],True),
            leaf('S0-01-BF-04','定位 retrieve()/消费路径','确认数据消费后索引如何推进或复位。',cap,10,['绑定 retrieve/等价函数'],True),
            leaf('S0-01-BF-05','定位 readFd()/readv()','确认 socket 数据如何进入 Buffer，以及额外栈缓冲/自适应读的实现。',cap,15,['绑定 readv/readFd 位置','说明大于当前 writable 空间的数据如何处理'],True),
            leaf('S0-01-BF-06','形成 Buffer 审计结论','说明 Buffer 已经解决的基础问题与 NebulaRPC 仍需重新验证的边界。',cap,15,['写入审计文档','至少绑定两个函数位置'],True),
        ]
    })
    groups.append({
        'id': 'audit', 'title': '6. 审计文档收束与证据检查',
        'description': '把前面的真实源码观察收束为可复用的历史能力边界。',
        'items': [
            leaf('S0-01-AU-01','完成“已经解决”章节','把 Reactor/TcpClient/Buffer/生命周期已经解决的能力逐条写清。',cap,15,['每条结论都不是单纯类名','每条关键结论至少有源码路径/函数'],True),
            leaf('S0-01-AU-02','完成“历史技术债”章节','记录旧实现仍需重新验证或不能原样搬入 NebulaRPC 的边界。',cap,15,['技术债必须来自实际源码观察','不提前讨论协程'],True),
            leaf('S0-01-AU-03','完成“可复用边界”章节','每个能力标记为：可直接复用思想 / 需要最小恢复 / 不能直接复用。',cap,15,['三类结论均给出依据'],True),
            leaf('S0-01-AU-04','补齐 git grep / IDE 调用链证据','把实际使用过的检索命令或 IDE 调用链记录写入文档末尾。',cap,15,['至少提供一种真实可复核证据','不能编造输出'],True),
            leaf('S0-01-AU-05','核对项目锚点路径','确认产物位于 NebulaRPC/docs/history/MYMUDUO_AUDIT.md，而不是 LearningCI/docs。',cap,5,['目标文件路径正确','文件可打开'],True),
            leaf('S0-01-AU-06','对照固定试卷做考前自检','只查看题目，不查答案，确认每题要求的证据都已经准备。',cap,10,['五道题都有对应学习/工程证据','不得提前让 AI 给答案'],False),
        ]
    })
    paper = {
        'paper_id': 'NRPC-S0-01-V1', 'version': 1, 'visible_from_start': True, 'frozen': True,
        'questions': [
            {'id':'q1','dimension':'explanation','max_score':15,'question':'基于你实际阅读到的 MyMuduo 源码，说明它在以下四个方面已经形成了什么能力边界：① Reactor / One Loop Per Thread；② TcpClient / Connector；③ TcpConnection 的非阻塞发送与接收；④ TcpConnection 生命周期与所有权。要求对每一项分别说明“已经解决到什么程度”和“这个结论为什么足以支持 NebulaRPC 不从零重做该能力”。不能只列类名或概念，必须结合真实对象之间的职责关系进行解释。'},
            {'id':'q2','dimension':'prediction','max_score':15,'question':'选择 MyMuduo 中一条真实的 TcpClient → TcpConnection 通信路径。假设已经建立连接，此时应用层连续提交多个发送请求，其中至少一个请求不能在第一次 socket 写操作中全部写完。禁止运行程序，先根据源码预测：后续数据会经过哪些对象和回调继续推进；哪些状态或事件会发生变化；后续什么条件出现时发送流程继续；连接在这段时间发生关闭时，已有发送状态会如何受到影响。提交预测时必须标出你依据的源码文件和函数名，但本题不要求修改代码。'},
            {'id':'q3','dimension':'implementation','max_score':25,'question':'完成 NebulaRPC/docs/history/MYMUDUO_AUDIT.md 中的 MyMuduo 历史能力审计。本次至少审计 EventLoop、TcpConnection、Connector、TcpClient、Buffer 五部分。每部分必须包含：① 已解决能力；② 真实调用关系或对象关系；③ 至少一个源码文件路径和函数名；④ 已发现的历史技术债或当前不能直接假定成立的边界；⑤ 对 NebulaRPC 的结论只能是“可直接复用思想/需要最小恢复/不能直接复用”三类之一，并给出依据。作为可验证证据，文档末尾必须附上本次实际使用的 git grep 命令及其输出摘要，或者 IDE 调用链记录；不得编造不存在的路径或函数。最终提交 MYMUDUO_AUDIT.md 的内容以及证据。'},
            {'id':'q4','dimension':'diagnosis','max_score':25,'question':'从 MyMuduo 的真实源码中任选一个与当前节点直接相关的历史实现问题进行诊断，范围只能是：partial write / output buffer / EPOLLOUT、TcpClient/Connector 事件驱动连接流程、TcpConnection 生命周期与所有权。诊断必须按照“观察到的实现 → 可能失效的具体场景 → 追踪到的源码路径 → 根因 → 当前实现是否已经解决 → NebulaRPC 是否仍需重新处理”六步完成。必须提供可验证依据，至少包含源码文件与函数名，并补充 git grep/IDE 调用链记录中的一种；如果你认为所选问题在 MyMuduo 中已经正确解决，也必须用源码证据证明，而不能只写结论。'},
            {'id':'q5','dimension':'transfer','max_score':20,'question':'假设现在开始 NebulaRPC 的最小网络 Runtime 恢复，但禁止直接复制整个 MyMuduo。仅根据本次源码审计结果，把以下能力逐项归类为“无需重新证明”“需要通过最小测试恢复”“必须重新设计后才能使用”：EventLoop/Channel 事件分发、One Loop Per Thread 所有权、TcpClient/Connector、Buffer、partial write/output buffer/EPOLLOUT、TcpConnection 生命周期。每项必须说明判断依据，并明确指出哪些旧实现即使能运行，也不能因此直接视为 NebulaRPC 已掌握的新能力。不得引入协程、RPC 协议或后续阶段技术。'}
        ]
    }
    return groups, paper


def generic_groups(node):
    cap = node['capability']
    evid = node.get('project_anchor', {}).get('evidence', [])
    evidence_hint = '、'.join(evid) if evid else '代码/测试/日志/文档证据'
    groups = []
    for idx, task in enumerate(node.get('tasks', []), start=1):
        gid=f'g{idx}'
        items=[
            leaf(f"{node['id']}-G{idx}-01", f'定位任务边界：{task[:28]}',
                 f'先定位完成“{task}”真正涉及的文件、函数、测试、脚本或文档位置；不开始相邻节点工作。', cap, 10,
                 ['列出实际涉及的文件/函数/命令','确认没有进入 Out of Scope'], True),
            leaf(f"{node['id']}-G{idx}-02", f'执行核心任务：{task[:28]}',
                 task, cap, 25,
                 [f'完成冻结任务：{task}', f'留下可复核的{evidence_hint}'], True),
            leaf(f"{node['id']}-G{idx}-03", f'记录验证结果：{task[:28]}',
                 '把执行结果、失败现象、最终结论和证据位置写入项目锚点规定的产物；如果本任务是实验，必须同时记录参数和结果。', cap, 15,
                 ['结论可以由第三方根据证据复核','记录至少一个实际证据位置'], True),
        ]
        groups.append({'id':gid,'title':f'{idx}. {task}','description':'由冻结计划中的最低任务展开。','items':items})
    must_items=[]
    for idx, concept in enumerate(node.get('must_learn', []), start=1):
        must_items.append(leaf(f"{node['id']}-M-{idx:02d}", f'闭卷确认：{concept}',
            f'不看答案，用自己的话写出“{concept}”的作用、边界、关键因果关系，并指出它在当前项目中的真实落点。', cap, 12,
            [f'能够解释 {concept} 为什么存在','能够指出真实项目落点','能够说明至少一个边界或失败场景'], False))
    if must_items:
        groups.append({'id':'must','title':'能力核对','description':'把“接触过”压缩成可闭卷解释的能力。','items':must_items})
    paths = node.get('project_anchor', {}).get('paths', [])
    path_text='、'.join(paths) if paths else '当前节点规定的项目锚点'
    groups.append({'id':'gate','title':'验收准备','description':'只检查当前节点证据是否齐全，不扩路线。','items':[
        leaf(f"{node['id']}-GATE-01",'核对工程产物完整性',f'确认 {path_text} 已存在且能被复核。',cap,10,['项目锚点产物存在','关键结论能追溯到证据'],True),
        leaf(f"{node['id']}-GATE-02",'核对 Out of Scope',f"确认本节点没有为了完成任务而进入：{'、'.join(node.get('out_of_scope', [])) or '未规定的相邻范围'}。",cap,5,['没有提交相邻节点成果冒充当前节点完成度'],False),
        leaf(f"{node['id']}-GATE-03",'对照固定试卷自检','提前查看固定正式验收题目，只检查证据是否准备，不向 AI 索要答案。',cap,8,['五个评分维度都有可用证据','implementation/diagnosis 的工程证据可复核'],False),
    ]})
    return groups


def generic_paper(node):
    must = '；'.join(node.get('must_learn', []))
    out = '；'.join(node.get('out_of_scope', []))
    paths = '、'.join(node.get('project_anchor', {}).get('paths', [])) or '当前节点规定的项目锚点'
    evidence = '、'.join(node.get('project_anchor', {}).get('evidence', [])) or '代码、测试、日志或实验记录'
    title=node['title']
    capability=node['capability']
    return {
        'paper_id': f"{node['id']}-V1", 'version':1, 'visible_from_start':True, 'frozen':True,
        'questions':[
            {'id':'q1','dimension':'explanation','max_score':15,'question':f'不查看总计划，用自己的话解释“{title}”的核心机制、它解决的问题以及边界。必须覆盖本节点 Must Learn：{must}。不能只背定义；需要结合 NebulaRPC 当前实现或设计说明因果关系。'},
            {'id':'q2','dimension':'prediction','max_score':15,'question':f'围绕“{title}”构造一个当前节点范围内的陌生变化场景：改变一个关键输入、时序、并发条件或故障条件。在实际运行前，先预测系统行为、关键状态变化和最可能失败的位置，并写出预测依据。不得进入本节点明确不考的范围：{out or "无"}。'},
            {'id':'q3','dimension':'implementation','max_score':25,'question':f'提交本节点规定的真实工程产物并证明它达到冻结计划的最低验收标准。项目锚点：{paths}。必须附可验证证据（至少一种：{evidence}），同时给出复现命令/步骤和实际结果；只描述“已经完成”不得分。'},
            {'id':'q4','dimension':'diagnosis','max_score':25,'question':f'从本节点真实实现、测试或实验中选择一个失败/异常/边界问题进行诊断。必须按“观察 → 假设 → 证据采集 → 根因 → 修复或结论 → 再验证”完成，并附真实可验证证据（{evidence}）。问题必须严格属于“{title}”范围。'},
            {'id':'q5','dimension':'transfer','max_score':20,'question':f'给出一个没有在训练任务中原样出现、但仍属于当前能力边界的新场景，说明如何把“{capability}”迁移过去。必须说明哪些原则保持不变、哪些参数或实现需要调整、有什么取舍；禁止借此提前进入：{out or "后续节点"}。'},
        ]
    }


def compile_node(node, plan_version):
    if node['id']=='NRPC-S0-01':
        groups,paper=custom_s001(node)
        compiler_status='REVIEWED'
    else:
        groups=generic_groups(node)
        paper=generic_paper(node)
        compiler_status='GENERATED'
    total_leaf=sum(len(g['items']) for g in groups)
    return {
        'schema_version': 1,
        'node_id': node['id'],
        'node_title': node['title'],
        'source_plan_version': plan_version,
        'source_section': node.get('source_section',''),
        'compiler': {
            'type': 'LearningCI 基础节点执行包生成器',
            'status': compiler_status,
            'note': 'S0-01 已人工细化；其余节点为基础草稿。接近执行窗口时，通过 LearningCI 导出细化包，交给 ChatGPT 单节点细化后再导回，不使用任何模型 API。'
        },
        'task_policy': {
            'single_active_leaf_task': True,
            'leaf_tasks_required_for_verification': True,
            'parent_progress_is_derived': True,
            'paper_visible_before_tasks_complete': True,
        },
        'task_groups': groups,
        'task_count': total_leaf,
        'verification_paper': paper,
        'retest_policy': {
            'reuse_initial_verification_for_failed_attempts': True,
            'new_paper_required_for_retest': True,
            'retest_paper_must_change_scenario': True,
        },
    }


def main():
    data=json.loads(PLAN_PATH.read_text(encoding='utf-8'))
    version=data['plan']['version']
    index=[]
    for node in data['nodes']:
        bundle=compile_node(node,version)
        out=OUT_DIR/f"{node['id']}.json"
        out.write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        index.append({'node_id':node['id'],'title':node['title'],'task_count':bundle['task_count'],'compiler_status':bundle['compiler']['status'],'paper_id':bundle['verification_paper']['paper_id']})
    (OUT_DIR/'index.json').write_text(json.dumps({'schema_version':1,'generated_at':'2026-09-16','nodes':index},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'已生成 {len(index)} 个节点执行包，共 {sum(x["task_count"] for x in index)} 个叶子任务')

if __name__=='__main__':
    main()
