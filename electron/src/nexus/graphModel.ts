import type { Edge, Node, XYPosition } from "@xyflow/react";
import { getSettingValue } from "../app/state";
import { SETTING_DEFINITIONS, SETTING_GROUPS, type SettingDefinition } from "../app/settingsCatalog";
import type { AppState, SettingGroup, SettingKey, SettingValue } from "../app/types";

export interface SettingGraphNodeData extends Record<string, unknown> {
  label: string;
  tag: string;
  caption: string;
  kind: "core" | "category" | "setting";
  group?: SettingGroup;
  setting?: SettingKey;
  value?: string;
}

export type SettingGraphNode = Node<SettingGraphNodeData, "settingCard">;

interface NodeDefinition {
  id: string;
  x: number;
  y: number;
  data: SettingGraphNodeData;
}

const CATEGORY_POSITIONS: Record<SettingGroup, XYPosition> = {
  appearance: { x: 360, y: 80 },
  application: { x: 250, y: 610 },
  voice: { x: 890, y: 95 },
  workspace: { x: 1180, y: 430 },
  ai: { x: 870, y: 760 },
  system: { x: 470, y: 850 }
};

const LEAF_POSITIONS: Record<SettingKey, XYPosition> = {
  interfaceMode: { x: 45, y: 0 },
  theme: { x: 45, y: 112 },
  density: { x: 45, y: 224 },
  corners: { x: 45, y: 336 },
  motion: { x: 45, y: 448 },
  appName: { x: 10, y: 545 },
  assistantName: { x: 10, y: 655 },
  testingMode: { x: 10, y: 765 },
  wakeWord: { x: 1190, y: -35 },
  microphone: { x: 1190, y: 80 },
  silenceSeconds: { x: 1190, y: 195 },
  workspaceRoot: { x: 1490, y: 365 },
  workspaceScope: { x: 1490, y: 480 },
  aiModel: { x: 1150, y: 690 },
  aiThinking: { x: 1150, y: 800 },
  contextTokens: { x: 1150, y: 910 },
  temperature: { x: 860, y: 1030 },
  language: { x: 170, y: 980 }
};

const CATEGORY_TAGS: Record<SettingGroup, string> = {
  appearance: "01",
  application: "02",
  voice: "03",
  workspace: "04",
  ai: "05",
  system: "06"
};

function prettyValue(value: SettingValue, field?: SettingDefinition): string {
  if (typeof value === "boolean") return value ? "ВКЛЮЧЕНО" : "ВЫКЛЮЧЕНО";
  if (field?.options) return field.options.find((option) => option.value === String(value))?.label ?? String(value);
  if (typeof value === "number") return String(value) + (field?.unit ? " " + field.unit : "");
  return String(value);
}

export function createSettingNodes(state: AppState): SettingGraphNode[] {
  const definitions: NodeDefinition[] = [
    {
      id: "core", x: 710, y: 415,
      data: { label: "SETTINGS CORE", tag: "ROOT", caption: "Единая модель настроек", kind: "core", value: "LOCAL / PREVIEW" }
    }
  ];

  for (const group of SETTING_GROUPS) {
    const position = CATEGORY_POSITIONS[group.id];
    const fields = SETTING_DEFINITIONS.filter((field) => field.group === group.id);
    definitions.push({
      id: group.id, x: position.x, y: position.y,
      data: {
        label: group.label.toUpperCase(),
        tag: CATEGORY_TAGS[group.id],
        caption: fields.length + " параметра · нажми для редактирования",
        kind: "category",
        group: group.id,
        value: fields.length + " НАСТРОЕК"
      }
    });

    fields.forEach((field, index) => {
      const leafPosition = LEAF_POSITIONS[field.key];
      const value = getSettingValue(state, field.key);
      definitions.push({
        id: field.key,
        x: leafPosition.x,
        y: leafPosition.y,
        data: {
          label: field.label,
          tag: CATEGORY_TAGS[group.id] + "." + (index + 1).toString().padStart(2, "0"),
          caption: field.description,
          kind: "setting",
          group: group.id,
          setting: field.key,
          value: prettyValue(value, field)
        }
      });
    });
  }

  let savedPositions: Record<string, XYPosition> = {};
  try {
    const raw = window.localStorage.getItem("jarvis.nexus.graph-layout.v1");
    if (raw) savedPositions = JSON.parse(raw) as Record<string, XYPosition>;
  } catch {
    savedPositions = {};
  }

  return definitions.map((definition) => ({
    id: definition.id,
    type: "settingCard",
    position: savedPositions[definition.id] ?? { x: definition.x, y: definition.y },
    data: definition.data
  }));
}

export function createSettingEdges(): Edge[] {
  const edges: Edge[] = SETTING_GROUPS.map((group) => ({
    id: "core-" + group.id,
    source: "core",
    target: group.id,
    type: "smoothstep",
    style: { stroke: "var(--graph-edge)", strokeWidth: 1.4 }
  }));

  for (const field of SETTING_DEFINITIONS) {
    edges.push({
      id: field.group + "-" + field.key,
      source: field.group,
      target: field.key,
      type: "smoothstep",
      style: { stroke: "var(--graph-edge)", strokeWidth: 1.2 }
    });
  }

  return edges;
}

export function getSettingsGroup(group: SettingGroup): { title: string; description: string } {
  const entry = SETTING_GROUPS.find((item) => item.id === group);
  return entry ? { title: entry.label, description: entry.description } : { title: "Настройки", description: "" };
}
