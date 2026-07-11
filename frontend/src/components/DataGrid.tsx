import { LayoutGrid } from 'lucide-react';

interface DataGridProps {
  data: any[];
  rowCount?: number;
}

export default function DataGrid({ data }: DataGridProps) {
  if (!Array.isArray(data) || data.length === 0) {
    return (
      <div className="datagrid-empty animate-fade-in">
        <div className="datagrid-empty-icon">
          <LayoutGrid size={24} />
        </div>
        <div className="datagrid-empty-title">No data to display</div>
        <div className="datagrid-empty-sub">
          Select a table from the sidebar to preview its rows here.
        </div>
      </div>
    );
  }

  const firstRow = data.find((row: any) => row && typeof row === 'object') ?? {};
  const columns = Object.keys(firstRow);

  return (
    <div className="datagrid-wrap animate-fade-in">
      <table className="datagrid-table">
        <thead>
          <tr>
            <th className="datagrid-rn" style={{ background: 'var(--table-header)', borderRight: '1px solid var(--border)' }}>#</th>
            {columns.map(col => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i}>
              <td className="datagrid-rn" style={{ borderRight: '1px solid rgba(42,45,62,0.4)' }}>{i + 1}</td>
              {columns.map(col => {
                const val = row[col];
                const isNull = val === null || val === undefined;
                return (
                  <td key={col} title={isNull ? 'NULL' : String(val)}>
                    {isNull
                      ? <span className="datagrid-null">null</span>
                      : String(val)
                    }
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}