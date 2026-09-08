import { useEffect, useRef } from "react";
import type { CharacterId, JointState, MotionId, Rig, RigNode, SceneId } from "./types";

interface PuppetStageProps {
  character: CharacterId;
  scene: SceneId;
  motion: MotionId;
  joints: JointState;
  playing: boolean;
}

type ImageMap = Map<string, HTMLImageElement>;

const STAGE_WIDTH = 1280;
const STAGE_HEIGHT = 720;

function loadImage(source: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`Unable to load ${source}`));
    image.src = source;
  });
}

function animatedRotation(nodeId: string, motion: MotionId, seconds: number): number {
  const beat = Math.sin(seconds * 4.2);
  const stride = Math.sin(seconds * 7);

  if (motion === "raise_hand") {
    if (nodeId === "upper_arm_r") return -66;
    if (nodeId === "lower_arm_r") return -26;
    if (nodeId === "head") return beat * 5;
  }
  if (motion === "walk") {
    if (nodeId === "leg_l") return stride * 22;
    if (nodeId === "leg_r") return -stride * 22;
    if (nodeId === "upper_arm_l") return -stride * 13;
    if (nodeId === "upper_arm_r") return stride * 13;
    if (nodeId === "torso") return beat * 2;
  }
  if (motion === "attack") {
    if (nodeId === "upper_arm_r") return -42 + beat * 20;
    if (nodeId === "lower_arm_r") return 18 + beat * 28;
    if (nodeId === "prop") return beat * 8;
    if (nodeId === "torso") return -5;
  }

  if (nodeId === "head") return beat * 3;
  if (nodeId === "torso") return beat * 1.4;
  if (nodeId === "upper_arm_l") return beat * 2;
  if (nodeId === "upper_arm_r") return -beat * 2;
  return 0;
}

function drawPuppet(
  context: CanvasRenderingContext2D,
  rig: Rig,
  images: ImageMap,
  motion: MotionId,
  joints: JointState,
  seconds: number
) {
  const nodesByParent = new Map<string | null, RigNode[]>();
  for (const node of rig.nodes) {
    const siblings = nodesByParent.get(node.parent) ?? [];
    siblings.push(node);
    nodesByParent.set(node.parent, siblings);
  }
  for (const siblings of nodesByParent.values()) siblings.sort((a, b) => a.zIndex - b.zIndex);

  const drawNode = (node: RigNode) => {
    const image = images.get(node.part);
    const manualOffset = node.id in joints ? joints[node.id as keyof JointState] : 0;
    const rotation = node.rotation + animatedRotation(node.id, motion, seconds) + manualOffset;

    context.save();
    context.translate(node.position.x, node.position.y);
    context.rotate((rotation * Math.PI) / 180);
    if (image) {
      context.drawImage(image, -node.pivot.x, -node.pivot.y);
    }
    for (const child of nodesByParent.get(node.id) ?? []) drawNode(child);
    context.restore();
  };

  const root = rig.nodes.find((node) => node.id === rig.root);
  if (root) drawNode(root);
}

export default function PuppetStage({ character, scene, motion, joints, playing }: PuppetStageProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const resourcesRef = useRef<{ rig: Rig; parts: ImageMap; background: HTMLImageElement } | null>(null);
  const valuesRef = useRef({ motion, joints, playing });

  useEffect(() => {
    valuesRef.current = { motion, joints, playing };
  }, [joints, motion, playing]);

  useEffect(() => {
    let cancelled = false;

    async function prepare() {
      const [manifestResponse, background] = await Promise.all([
        fetch(`/characters/${character}/manifest.json`),
        loadImage(`/backgrounds/${scene}.png`)
      ]);
      if (!manifestResponse.ok) throw new Error(`Unable to load manifest for ${character}`);
      const manifest = (await manifestResponse.json()) as { rig: string };
      const rigResponse = await fetch(`/characters/${character}/${manifest.rig}`);
      if (!rigResponse.ok) throw new Error(`Unable to load rig for ${character}`);
      const rig = (await rigResponse.json()) as Rig;
      const images = await Promise.all(rig.nodes.map((node) => loadImage(`/characters/${character}/${node.part}`)));
      if (!cancelled) {
        resourcesRef.current = {
          rig,
          background,
          parts: new Map(rig.nodes.map((node, index) => [node.part, images[index]]))
        };
      }
    }

    resourcesRef.current = null;
    void prepare().catch(() => {
      resourcesRef.current = null;
    });
    return () => {
      cancelled = true;
    };
  }, [character, scene]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    let frame = 0;

    const render = (time: number) => {
      const resources = resourcesRef.current;
      context.clearRect(0, 0, STAGE_WIDTH, STAGE_HEIGHT);
      if (resources) {
        context.drawImage(resources.background, 0, 0, STAGE_WIDTH, STAGE_HEIGHT);
        context.save();
        context.translate(320, 0);
        context.scale(1.03, 1.03);
        context.shadowColor = "rgba(28, 12, 18, 0.55)";
        context.shadowBlur = 18;
        context.shadowOffsetY = 9;
        const state = valuesRef.current;
        const seconds = state.playing ? time / 1000 : 0;
        drawPuppet(context, resources.rig, resources.parts, state.motion, state.joints, seconds);
        context.restore();
      } else {
        context.fillStyle = "#182d2f";
        context.fillRect(0, 0, STAGE_WIDTH, STAGE_HEIGHT);
      }
      frame = requestAnimationFrame(render);
    };
    frame = requestAnimationFrame(render);
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <div className="stage-shell">
      <canvas
        aria-label="皮影戏舞台"
        className="stage-canvas"
        height={STAGE_HEIGHT}
        ref={canvasRef}
        width={STAGE_WIDTH}
      />
      <div className="stage-vignette" />
      <div className="stage-watermark">光影新生</div>
      <div className="stage-status">
        <span className={playing ? "status-dot is-live" : "status-dot"} />
        {playing ? "演出进行中" : "舞台已暂停"}
      </div>
    </div>
  );
}
