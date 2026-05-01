export async function onRequest() {
  return new Response(
    JSON.stringify({ status: 'ok', message: '세무판례 API 서버 정상 작동 중' }),
    {
      status: 200,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
      },
    }
  );
}
