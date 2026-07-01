import { useState } from 'react';
import type { KnowledgeCatalog } from '../api/types';
import type { ViewId } from '../types';

interface SidebarProps {
  catalog: KnowledgeCatalog | null;
  activeView: ViewId;
  onSelectView: (view: ViewId) => void;
}

type FolderId = 'sessions' | 'sources' | 'graph';

export function Sidebar({ catalog, activeView, onSelectView }: SidebarProps) {
  const [openFolders, setOpenFolders] = useState<Record<FolderId, boolean>>({
    sessions: true,
    sources: false,
    graph: false,
  });

  const toggleFolder = (id: FolderId) =>
    setOpenFolders((prev) => ({ ...prev, [id]: !prev[id] }));

  // Prefer real curriculum content from the backend; fall back to the preview
  // sample so the shell still reads correctly before any domain is fetched.
  const domain = catalog?.domains?.[0] ?? null;
  const firstChapter = domain?.chapters?.[0] ?? null;
  const domainName = domain ? titleCase(domain.id) : 'Math';
  const domainMeta = domain
    ? `${domain.chapters.length} chapter${domain.chapters.length === 1 ? '' : 's'}`
    : 'Discrete math for proof-based CS';
  const sourceFiles = firstChapter?.source_files ?? ['lecture-01.pdf', 'sets-video.mp4', 'mit-set-notes.html'];
  const sourceCount = firstChapter?.source_count ?? sourceFiles.length;
  const graphCount = firstChapter?.wiki_count ?? 8;

  return (
    <aside className="sidebar">
      <div className="domain-list">
        <section className="domain-card">
          <div className="domain-row">
            <div>
              <div className="domain-name">{domainName}</div>
              <div className="domain-meta">{domainMeta}</div>
            </div>
            <span className="tree-count">{firstChapter ? firstChapter.id : '0.51'}</span>
          </div>

          <div className="tree">
            <FolderButton
              label="Session History"
              count={2}
              open={openFolders.sessions}
              onClick={() => toggleFolder('sessions')}
            />
            <div className={folderClass(openFolders.sessions)}>
              <TreeLeaf
                icon="C"
                label="Discrete Math Tutor Chat"
                active={activeView === 'chat'}
                onClick={() => onSelectView('chat')}
              />
              <TreeLeaf
                icon="S"
                label="Set Theory Scratchpad"
                active={activeView === 'scratchpad'}
                onClick={() => onSelectView('scratchpad')}
              />
            </div>

            <FolderButton
              label="GroundedWiki Sources"
              count={sourceCount}
              open={openFolders.sources}
              onClick={() => {
                toggleFolder('sources');
                onSelectView('sources');
              }}
              active={activeView === 'sources'}
            />
            <div className={folderClass(openFolders.sources)}>
              {sourceFiles.map((name) => (
                <TreeLeaf key={name} icon={fileIcon(name)} label={name} />
              ))}
            </div>

            <FolderButton
              label="Curriculum Graph"
              count={graphCount}
              open={openFolders.graph}
              onClick={() => toggleFolder('graph')}
            />
            <div className={folderClass(openFolders.graph)}>
              <TreeLeaf
                icon="G"
                label="Curriculum Map"
                active={activeView === 'graph'}
                onClick={() => onSelectView('graph')}
              />
            </div>
          </div>
        </section>

        <button className="button-secondary" onClick={() => onSelectView('create')}>
          New domain
        </button>
      </div>
    </aside>
  );
}

interface FolderButtonProps {
  label: string;
  count: number;
  open: boolean;
  active?: boolean;
  onClick: () => void;
}

function FolderButton({ label, count, open, active, onClick }: FolderButtonProps) {
  return (
    <button
      className={`tree-row${open || active ? ' is-active' : ''}`}
      aria-expanded={open}
      onClick={onClick}
    >
      <span className="tree-icon">{open ? '▾' : '▸'}</span>
      <span>{label}</span>
      <span className="tree-count">{count}</span>
    </button>
  );
}

interface TreeLeafProps {
  icon: string;
  label: string;
  active?: boolean;
  onClick?: () => void;
}

function TreeLeaf({ icon, label, active, onClick }: TreeLeafProps) {
  return (
    <button className={`tree-row${active ? ' is-active' : ''}`} onClick={onClick}>
      <span className="tree-icon">{icon}</span>
      <span>{label}</span>
      <span />
    </button>
  );
}

function folderClass(open: boolean): string {
  return `folder-content${open ? ' is-open' : ''}`;
}

function titleCase(value: string): string {
  return value
    .split(/[-_\s]+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function fileIcon(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  if (ext === 'pdf') return 'P';
  if (['mp4', 'mov', 'avi', 'mp3', 'wav'].includes(ext)) return 'V';
  if (['html', 'htm'].includes(ext)) return 'W';
  if (['md', 'txt'].includes(ext)) return 'T';
  return 'F';
}
