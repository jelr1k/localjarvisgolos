import { useEffect, useMemo, useState } from "react";
import { Background, Controls, Handle, MiniMap, Position, ReactFlow, useNodesState, type Node, type NodeProps } from "@xyflow/react";
import { ArrowRight, Focus, MousePointer2, RotateCcw, Workflow } from "lucide-react";
import { useAppState } from "../app/context";
import { getSettingDefinition, SETTING_DEFINITIONS } from "../app/settingsCatalog";
import type { SettingDefinition } from "../app/settingsCatalog";
import { getSettingValue } from "../app/state";
import type { SettingGroup } from "../app/types";
import { SettingsField } from "../components/SettingsField";
import { PrototypeNotice } from "../components/PrototypeNotice";
import { createSettingEdges, createSettingNodes, getSettingsGroup, type SettingGraphNode } from "./graphModel";

function SettingGraphNodeView({ data, selected }: NodeProps<SettingGraphNode>) {
  return (
    <>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <div className={"setting-graph-node setting-graph-node-" + data.kind + (selected ? " is-selected" : "")}>
        <div className="graph-node-header"><span>{data.tag}</span>{data.kind === "core" && <Workflow size={14} />}</div>
        <strong>{data.label}</strong>
        <small>{data.value || data.caption}</small>
        {data.kind === "setting" && <span className="graph-node-edit">ОТКРЫТЬ ПАРАМЕТР</span>}
      </div>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </>
  );
}

const nodeTypes = { settingCard: SettingGraphNodeView };
const edges = createSettingEdges();

function Inspector({ node, onChooseGroup }: { node: SettingGraphNode | undefined; onChooseGroup: (id: string) => void }) {
  if (!node || node.id === "core") {
    return (
      <aside className="nexus-inspector">
        <div className="inspector-heading"><span className="eyebrow">INSPECTOR / ROOT</span><h2>Центр настроек</h2><p>Все элементы карты читают и изменяют одну модель состояния. Выбери категорию или отдельный параметр.</p></div>
        <div className="inspector-status"><span className="status-dot" /> ЕДИНОЕ СОСТОЯНИЕ</div>
        <div className="inspector-quicklinks">
          {(["appearance", "application", "voice", "workspace", "ai", "system"] as SettingGroup[]).map((group) => {
            const meta = getSettingsGroup(group);
            return <button key={group} type="button" onClick={() => onChooseGroup(group)}><span>{meta.title}</span><ArrowRight size={14} /></button>;
          })}
        </div>
        <div className="inspector-note">Перетаскивай узлы мышью, двигай холст и приближай карту колёсиком. Координаты узлов сохраняются локально.</div>
      </aside>
    );
  }

  const fields: SettingDefinition[] = node.data.setting
    ? [getSettingDefinition(node.data.setting)]
    : node.data.group
      ? SETTING_DEFINITIONS.filter((field) => field.group === node.data.group)
      : [];
  const heading = node.data.group ? getSettingsGroup(node.data.group) : { title: node.data.label, description: node.data.caption };

  return (
    <aside className="nexus-inspector">
      <div className="inspector-heading"><span className="eyebrow">INSPECTOR / {node.data.tag}</span><h2>{heading.title}</h2><p>{node.data.setting ? getSettingDefinition(node.data.setting).description : heading.description}</p></div>
      <div className="inspector-fields">
        {fields.length > 0 ? fields.map((field) => <SettingsField key={field.key} field={field} compact />) : <p className="inspector-empty">У этой группы пока нет доступных полей.</p>}
      </div>
      {node.data.group && !node.data.setting && <div className="inspector-footer"><span>{fields.length.toString().padStart(2, "0")} ПАРАМЕТРА</span><button type="button" onClick={() => onChooseGroup("core")}>К общей карте <ArrowRight size={13} /></button></div>}
    </aside>
  );
}

export function SettingsGraph() {
  const { state } = useAppState();
  const [nodes, setNodes, onNodesChange] = useNodesState<SettingGraphNode>(createSettingNodes(state));
  const [selectedNodeId, setSelectedNodeId] = useState("core");
  const layoutKey = "jarvis.nexus.graph-layout.v1";

  useEffect(() => {
    setNodes((currentNodes) => currentNodes.map((node) => {
      if (!node.data.setting) return node;
      const field = getSettingDefinition(node.data.setting);
      const value = getSettingValue(state, node.data.setting);
      let formatted = String(value);
      if (typeof value === "boolean") formatted = value ? "ВКЛЮЧЕНО" : "ВЫКЛЮЧЕНО";
      else if (field.options) formatted = field.options.find((option) => option.value === String(value))?.label ?? String(value);
      else if (typeof value === "number") formatted = String(value) + (field.unit ? " " + field.unit : "");
      return { ...node, data: { ...node.data, value: formatted } };
    }));
  }, [state.settings, state.interfaceMode, setNodes]);

  const selectedNode = nodes.find((node) => node.id === selectedNodeId);
  const onNodeDragStop = (_event: MouseEvent | TouchEvent, draggedNode: SettingGraphNode) => {
    const positions: Record<string, { x: number; y: number }> = {};
    nodes.forEach((node) => { positions[node.id] = node.id === draggedNode.id ? draggedNode.position : node.position; });
    positions[draggedNode.id] = draggedNode.position;
    try {
      window.localStorage.setItem(layoutKey, JSON.stringify(positions));
    } catch (error) {
      console.warn("Не удалось сохранить расположение узлов.", error);
    }
  };
  const onChooseGroup = (id: string) => setSelectedNodeId(id);
  const miniMapColor = useMemo(() => (node: Node) => {
    const graphNode = node as SettingGraphNode;
    if (graphNode.data.kind === "core") return "#d9a76b";
    if (graphNode.data.kind === "category") return "#638a93";
    return graphNode.id === selectedNode?.id ? "#d9a76b" : "#43515a";
  }, [selectedNode?.id]);

  return (
    <div className="nexus-settings-page">
      <div className="nexus-settings-heading">
        <div><span className="eyebrow">NEXUS / CONFIGURATION MAP</span><h1>Настройки.</h1><p>Параметры разложены по узлам, как заметки в графе. Нажми узел, чтобы открыть его настройки.</p></div>
        <div className="nexus-graph-hint"><MousePointer2 size={15} /> ПАНОРАМА <span>·</span> МАСШТАБ <span>·</span> ПЕРЕТАСКИВАНИЕ</div>
      </div>
      <PrototypeNotice compact />
      <div className="nexus-settings-workspace">
        <section className="nexus-graph-panel" aria-label="Граф настроек">
          <div className="nexus-graph-toolbar"><span><Workflow size={15} /> SETTINGS GRAPH <b>{nodes.length.toString().padStart(2, "0")} NODES</b></span><button type="button" onClick={() => setSelectedNodeId("core")} title="Выбрать корневой узел"><Focus size={14} /> ROOT</button><button type="button" onClick={() => { try { window.localStorage.removeItem(layoutKey); } catch {} window.location.reload(); }} title="Сбросить расположение узлов"><RotateCcw size={14} /> RESET</button></div>
          <div className="nexus-graph-canvas">
            <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange}
              onNodeClick={(_event, node) => setSelectedNodeId(node.id)}
              onNodeDragStop={onNodeDragStop}
              nodesConnectable={false} fitView fitViewOptions={{ padding: 0.18 }} minZoom={0.18} maxZoom={1.8}
              defaultEdgeOptions={{ type: "smoothstep" }}>
              <Background color="var(--graph-dot)" gap={23} size={1} />
              <Controls showInteractive={false} />
              <MiniMap pannable zoomable nodeColor={miniMapColor} />
            </ReactFlow>
          </div>
        </section>
        <Inspector node={selectedNode} onChooseGroup={onChooseGroup} />
      </div>
      <div className="nexus-graph-footer"><span>ДАННЫЕ ХРАНЯТСЯ В ЛОКАЛЬНЫХ НАСТРОЙКАХ ОКНА</span><span>НАСТРОЙКИ НЕ ПЕРЕДАЮТСЯ BACKEND</span></div>
    </div>
  );
}
