import Konva from 'konva';
import type {
  ScratchpadExportBounds,
  ScratchpadNode,
} from '../../api/types';
import { selectedExportBounds } from './scratchpadModel';

export function createKonvaNode(node: ScratchpadNode): Konva.Group {
  const group = new Konva.Group({
    id: node.id,
    x: node.x,
    y: node.y,
    rotation: node.rotation ?? 0,
    scaleX: node.scale_x ?? 1,
    scaleY: node.scale_y ?? 1,
  });
  let child: Konva.Shape;
  if (node.type === 'stroke') {
    child = new Konva.Line({
      points: node.points,
      stroke: node.stroke,
      strokeWidth: node.stroke_width,
      lineCap: 'round',
      lineJoin: 'round',
      tension: 0.35,
    });
  } else if (node.type === 'text') {
    child = new Konva.Text({
      text: node.text,
      fill: node.fill,
      fontSize: node.font_size,
      width: node.width,
      height: node.height,
      fontFamily: 'CursorGothic, system-ui, sans-serif',
    });
  } else if (node.type === 'ellipse') {
    child = new Konva.Ellipse({
      x: node.width / 2,
      y: node.height / 2,
      radiusX: Math.abs(node.width / 2),
      radiusY: Math.abs(node.height / 2),
      stroke: node.stroke,
      strokeWidth: node.stroke_width,
    });
  } else if (node.type === 'line') {
    child = new Konva.Line({
      points: [0, 0, node.width, node.height],
      stroke: node.stroke,
      strokeWidth: node.stroke_width,
      lineCap: 'round',
    });
  } else {
    child = new Konva.Rect({
      width: node.width,
      height: node.height,
      stroke: node.stroke,
      strokeWidth: node.stroke_width,
    });
  }
  group.add(child);
  return group;
}

export function konvaSelectionBounds(
  nodes: ScratchpadNode[],
  selectedIds: string[],
  padding: number,
): ScratchpadExportBounds | null {
  const bounds = selectedExportBounds(nodes, selectedIds, padding);
  if (!bounds) return null;
  const x = Math.floor(bounds.x);
  const y = Math.floor(bounds.y);
  const right = Math.ceil(bounds.x + bounds.width);
  const bottom = Math.ceil(bounds.y + bounds.height);
  return {
    x,
    y,
    width: right - x,
    height: bottom - y,
    padding,
  };
}

export function konvaClientRectsBounds(
  rects: Array<{ x: number; y: number; width: number; height: number }>,
  padding: number,
): ScratchpadExportBounds | null {
  if (rects.length === 0) return null;
  const x = Math.floor(Math.min(...rects.map((rect) => rect.x)) - padding);
  const y = Math.floor(Math.min(...rects.map((rect) => rect.y)) - padding);
  const right = Math.ceil(
    Math.max(...rects.map((rect) => rect.x + rect.width)) + padding,
  );
  const bottom = Math.ceil(
    Math.max(...rects.map((rect) => rect.y + rect.height)) + padding,
  );
  return { x, y, width: right - x, height: bottom - y, padding };
}

export function exportKonvaSelection(
  nodes: ScratchpadNode[],
  selectedIds: string[],
  background: string,
  padding = 12,
): { imageDataUri: string; bounds: ScratchpadExportBounds } | null {
  const selected = new Set(selectedIds);
  const selectedNodes = nodes
    .filter((node) => selected.has(node.id))
    .map(createKonvaNode);
  const bounds = konvaClientRectsBounds(
    selectedNodes.map((node) => node.getClientRect()),
    padding,
  );
  if (!bounds) return null;
  const container = document.createElement('div');
  const stage = new Konva.Stage({
    container,
    width: Math.ceil(bounds.width),
    height: Math.ceil(bounds.height),
  });
  const backgroundLayer = new Konva.Layer();
  backgroundLayer.add(
    new Konva.Rect({
      x: 0,
      y: 0,
      width: bounds.width,
      height: bounds.height,
      fill: background,
    }),
  );
  const contentLayer = new Konva.Layer({ x: -bounds.x, y: -bounds.y });
  selectedNodes.forEach((node) => contentLayer.add(node));
  stage.add(backgroundLayer);
  stage.add(contentLayer);
  stage.draw();
  const imageDataUri = stage.toDataURL({
    mimeType: 'image/png',
    pixelRatio: 2,
  });
  stage.destroy();
  return { imageDataUri, bounds };
}
