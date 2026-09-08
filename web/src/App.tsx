import { useState } from "react";
import {
  Activity,
  ChevronDown,
  CircleDot,
  Cog,
  Hand,
  Maximize2,
  Moon,
  Pause,
  Play,
  RotateCcw,
  Sparkles,
  Swords,
  Trees,
  UserRound,
  WandSparkles
} from "lucide-react";
import PuppetStage from "./PuppetStage";
import type { CharacterId, JointId, JointState, MotionId, SceneId } from "./types";

const characters: { id: CharacterId; name: string; role: string }[] = [
  { id: "hero_rabbit", name: "赤绡兔将", role: "主角" },
  { id: "forest_fox", name: "青岚狐生", role: "客角" }
];

const scenes: { id: SceneId; name: string; Icon: typeof Moon }[] = [
  { id: "paper_curtain", name: "绛幕戏台", Icon: Sparkles },
  { id: "mountain_pass", name: "远山关隘", Icon: Trees },
  { id: "moon_bridge", name: "月桥夜渡", Icon: Moon }
];

const motions: { id: MotionId; name: string; Icon: typeof Hand }[] = [
  { id: "idle", name: "待场", Icon: CircleDot },
  { id: "raise_hand", name: "拱手", Icon: Hand },
  { id: "walk", name: "行步", Icon: Activity },
  { id: "attack", name: "亮相", Icon: Swords }
];

const jointControls: { id: JointId; name: string; min: number; max: number }[] = [
  { id: "head", name: "头部", min: -24, max: 24 },
  { id: "upper_arm_l", name: "左臂", min: -42, max: 42 },
  { id: "upper_arm_r", name: "右臂", min: -42, max: 42 },
  { id: "torso", name: "躯干", min: -12, max: 12 }
];

const initialJoints: JointState = { head: 0, upper_arm_l: 0, upper_arm_r: 0, torso: 0 };

export default function App() {
  const [character, setCharacter] = useState<CharacterId>("hero_rabbit");
  const [scene, setScene] = useState<SceneId>("moon_bridge");
  const [motion, setMotion] = useState<MotionId>("idle");
  const [joints, setJoints] = useState<JointState>(initialJoints);
  const [playing, setPlaying] = useState(true);
  const [gestureConnected, setGestureConnected] = useState(true);

  const currentCharacter = characters.find((item) => item.id === character)!;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-mark"><WandSparkles size={19} strokeWidth={1.8} /></span>
          <div>
            <p className="brand-eyebrow">AI INTERACTIVE SHADOW PLAY</p>
            <h1>光影戏台</h1>
          </div>
        </div>
        <div className="show-meta">
          <span className="show-title">《月下寻踪》</span>
          <span className="divider" />
          <span className="scene-title">第二幕 · 夜渡月桥</span>
        </div>
        <div className="top-actions">
          <button
            aria-pressed={gestureConnected}
            className={gestureConnected ? "connection is-connected" : "connection"}
            onClick={() => setGestureConnected((value) => !value)}
            type="button"
          >
            <span className="connection-dot" />
            {gestureConnected ? "手势已连接" : "手势未连接"}
          </button>
          <button aria-label="舞台设置" className="icon-button" title="舞台设置" type="button">
            <Cog size={18} />
          </button>
        </div>
      </header>

      <section className="workspace">
        <aside className="left-panel">
          <section className="panel-section cast-section">
            <div className="section-heading">
              <span>角色</span>
              <button aria-label="展开角色库" className="quiet-icon" title="展开角色库" type="button"><ChevronDown size={16} /></button>
            </div>
            <div className="character-list">
              {characters.map((item) => (
                <button
                  className={item.id === character ? "character-choice is-selected" : "character-choice"}
                  key={item.id}
                  onClick={() => setCharacter(item.id)}
                  type="button"
                >
                  <img alt="" src={`/characters/${item.id}/preview.png`} />
                  <span className="character-copy"><strong>{item.name}</strong><small>{item.role}</small></span>
                  <span className="choice-dot" />
                </button>
              ))}
            </div>
          </section>

          <section className="panel-section scene-section">
            <div className="section-heading"><span>场景</span><span className="count-label">{scenes.length}</span></div>
            <div className="scene-list">
              {scenes.map(({ id, name, Icon }) => (
                <button
                  className={id === scene ? "scene-choice is-selected" : "scene-choice"}
                  key={id}
                  onClick={() => setScene(id)}
                  type="button"
                >
                  <img alt="" src={`/backgrounds/${id}.png`} />
                  <span><Icon size={15} />{name}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="signal-card">
            <span className="signal-icon"><Hand size={18} /></span>
            <span><strong>{gestureConnected ? "动作捕捉正常" : "动作捕捉离线"}</strong><small>{gestureConnected ? "追踪稳定" : "使用舞台控制"}</small></span>
          </section>
        </aside>

        <section className="stage-area">
          <div className="stage-toolbar">
            <div><span className="toolbar-label">当前角色</span><strong>{currentCharacter.name}</strong></div>
            <div className="toolbar-actions">
              <button aria-label="重置姿态" className="icon-button" onClick={() => setJoints(initialJoints)} title="重置姿态" type="button"><RotateCcw size={17} /></button>
              <button aria-label="全屏舞台" className="icon-button" title="全屏舞台" type="button"><Maximize2 size={17} /></button>
            </div>
          </div>
          <PuppetStage character={character} joints={joints} motion={motion} playing={playing} scene={scene} />
          <div className="timeline-strip">
            <div className="timeline-label"><span className="record-dot" />演出轨</div>
            <div className="timeline"><span className="timeline-progress" /><i /></div>
            <time>00:42</time>
          </div>
        </section>

        <aside className="right-panel">
          <section className="panel-section action-section">
            <div className="section-heading"><span>动作</span><span className="count-label">实时</span></div>
            <div className="motion-grid">
              {motions.map(({ id, name, Icon }) => (
                <button
                  aria-pressed={id === motion}
                  className={id === motion ? "motion-button is-selected" : "motion-button"}
                  key={id}
                  onClick={() => setMotion(id)}
                  type="button"
                >
                  <Icon size={19} />
                  <span>{name}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="panel-section joints-section">
            <div className="section-heading"><span>关节微调</span><UserRound size={15} /></div>
            <div className="joint-list">
              {jointControls.map((joint) => (
                <label className="joint-control" key={joint.id}>
                  <span><strong>{joint.name}</strong><output>{joints[joint.id]}°</output></span>
                  <input
                    max={joint.max}
                    min={joint.min}
                    onChange={(event) => setJoints((values) => ({ ...values, [joint.id]: Number(event.target.value) }))}
                    type="range"
                    value={joints[joint.id]}
                  />
                </label>
              ))}
            </div>
          </section>

          <section className="performance-controls">
            <button className="play-button" onClick={() => setPlaying((value) => !value)} type="button">
              {playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
              {playing ? "暂停演出" : "继续演出"}
            </button>
            <button aria-label="重置舞台" className="reset-button" onClick={() => { setJoints(initialJoints); setMotion("idle"); }} title="重置舞台" type="button"><RotateCcw size={18} /></button>
          </section>
        </aside>
      </section>
    </main>
  );
}
