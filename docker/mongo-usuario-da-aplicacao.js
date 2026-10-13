// Roda uma vez, na primeira subida do volume do MongoDB (docker-entrypoint-initdb.d).
// Cria o usuário que a aplicação usa: lê e grava só no banco dela, sem poderes de administrador.
const banco = process.env.MONGO_APP_DB;
db.getSiblingDB(banco).createUser({
  user: process.env.MONGO_APP_USER,
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: [{ role: "readWrite", db: banco }],
});
