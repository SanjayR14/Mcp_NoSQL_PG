const API_URL = "http://localhost:8000";

export const connectToDb = async (details: any) => {
  const res = await fetch(`${API_URL}/api/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(details)
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
};

export const getStructure = async () => {
  const res = await fetch(`${API_URL}/api/structure`);
  return res.json();
};

export const getTables = async (connection: any) => {
  const res = await fetch(`${API_URL}/api/db-tables`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(connection)
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || 'Failed to load tables');
  }

  const json = await res.json();
  return json.tables ?? [];
};

export const previewTable = async (connection: any, table: string) => {
  const body = {
    ...connection,
    table,
  };

  const res = await fetch(`${API_URL}/api/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || 'Failed to preview table');
  }

  const json = await res.json();
  return json.data ?? json;
};