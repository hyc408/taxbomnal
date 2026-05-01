export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  const oc = url.searchParams.get('oc') || '';
  const id = url.searchParams.get('id') || '';

  /* CORS preflight */
  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: corsHeaders(),
    });
  }

  if (!oc || !id) {
    return json({ error: 'oc, id 파라미터가 필요합니다.' }, 400);
  }

  const target =
    `https://www.law.go.kr/DRF/lawService.do` +
    `?OC=${encodeURIComponent(oc)}` +
    `&target=prec` +
    `&ID=${encodeURIComponent(id)}` +
    `&type=JSON`;

  try {
    const res  = await fetch(target);
    const text = await res.text();
    return new Response(text, {
      status: 200,
      headers: { 'Content-Type': 'application/json; charset=utf-8', ...corsHeaders() },
    });
  } catch (err) {
    return json({ error: err.message }, 500);
  }
}

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...corsHeaders() },
  });
}
