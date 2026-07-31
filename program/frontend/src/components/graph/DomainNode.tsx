import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { DomainFlowNode } from './layout';

export function DomainNode({ data }: NodeProps<DomainFlowNode>) {
  return (
    <div className="graph-node graph-node--domain">
      <span className="graph-node__eyebrow">Domain</span>
      <span className="graph-node__title" title={data.label}>
        {data.label}
      </span>
      <Handle type="source" position={Position.Bottom} isConnectable={false} />
    </div>
  );
}
