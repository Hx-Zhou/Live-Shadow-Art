import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url));
const types={'.html':'text/html; charset=utf-8','.mjs':'text/javascript','.js':'text/javascript','.css':'text/css','.json':'application/json','.wasm':'application/wasm','.task':'application/octet-stream'};
http.createServer(async(req,res)=>{try{
 const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
 if(name==='/'){res.writeHead(302,{Location:'/web/index.html'}).end();return;}
 const file=path.resolve(root,'.'+(name==='/'?'/web/index.html':name));
 if(!file.startsWith(root)){res.writeHead(403).end();return;}
 const data=await readFile(file);res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'});res.end(data);
}catch{res.writeHead(404).end('Not found');}}).listen(8765,'127.0.0.1',()=>console.log('Open http://localhost:8765'));
