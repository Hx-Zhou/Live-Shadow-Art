export type CharacterId = "hero_rabbit" | "forest_fox";
export type SceneId = "paper_curtain" | "mountain_pass" | "moon_bridge";
export type MotionId = "idle" | "raise_hand" | "walk" | "attack";

export type JointId = "head" | "upper_arm_l" | "upper_arm_r" | "torso";

export type JointState = Record<JointId, number>;

export interface RigNode {
  id: string;
  parent: string | null;
  part: string;
  position: { x: number; y: number };
  pivot: { x: number; y: number };
  rotation: number;
  limits: { min: number; max: number };
  zIndex: number;
}

export interface Rig {
  id: string;
  name: string;
  type: "humanoid" | "animal";
  canvas: { width: number; height: number };
  root: string;
  nodes: RigNode[];
}
