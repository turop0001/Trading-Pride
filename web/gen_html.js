// Собирает lib/html.js из private/*.html. Запускать после правки страниц: node gen_html.js
const fs = require('fs');
const out = { pult: fs.readFileSync(__dirname + '/private/pult.html', 'utf8'), friend: fs.readFileSync(__dirname + '/private/friend.html', 'utf8') };
fs.writeFileSync(__dirname + '/lib/html.js', '// СГЕНЕРИРОВАНО gen_html.js из private/*.html — не править руками\nmodule.exports = ' + JSON.stringify(out) + ';\n');
