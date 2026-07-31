import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { ChapterFlowNode } from './layout';

export function ChapterNode({ data }: NodeProps<ChapterFlowNode>) {
  const { masteryPct, conceptsProficient, conceptsTotal, hasConceptGraph } = data;

  return (
    <div className="graph-node graph-node--chapter">
      <Handle type="target" position={Position.Top} isConnectable={false} />
      <span className="graph-node__eyebrow">Chapter</span>
      <span className="graph-node__title" title={data.label}>
        {data.label}
      </span>

      {hasConceptGraph && conceptsTotal > 0 ? (
        <div className="graph-chapter__mastery">
          <div className="graph-chapter__meter" aria-hidden="true">
            <div
              className="graph-chapter__meter-fill"
              style={{ transform: `scaleX(${masteryPct / 100})` }}
            />
          </div>
          <div className="graph-chapter__stats">
            <span className="graph-chapter__pct">{masteryPct}%</span>
            <span className="graph-chapter__count">
              {conceptsProficient}/{conceptsTotal} proficient
            </span>
          </div>
        </div>
      ) : (
        <span className="graph-chapter__uncompiled">Not compiled</span>
      )}

      <Handle type="source" position={Position.Bottom} isConnectable={false} />
    </div>
  );
}
