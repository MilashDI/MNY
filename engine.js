(function(root){
const roles={civil:'Мирный житель',sheriff:'Шериф',mafia:'Мафия',don:'Дон'};
const black=p=>['mafia','don'].includes(p.role);
function create(ids){return {id:Date.now().toString(),created:new Date().toISOString(),phase:'setup',day:-1,roundVersion:2,opener:0,speaker:0,spoken:[],nominated:[],ballot:null,nights:[],log:[],winner:null,timer:{elapsed:0,started:null},seats:ids.map((id,i)=>({id,number:i+1,role:'civil',alive:true,fouls:0,technicalFoul:false,muteDay:null,reason:null}))};}
function nextAlive(g,n){for(let k=1;k<=10;k++){let i=(n+k)%10;if(g.seats[i].alive)return i;}return null;}
function startDay(g){g.opener=g.day<0?(g.seats[0].alive?0:nextAlive(g,0)):nextAlive(g,g.opener);g.day++;g.phase='day';g.speaker=g.opener;g.spoken=[];g.nominated=[];g.ballot=null;}
function foul(g,i){const p=g.seats[i];if(!p.alive||p.fouls>=3)return;p.fouls++;if(p.fouls===3)p.muteDay=g.phase==='day'&&!g.spoken.includes(i)?g.day:g.day+1;}
function remove(g,i,reason){g.seats[i].alive=false;g.seats[i].reason=reason;}
function winner(g){const alive=g.seats.filter(p=>p.alive),b=alive.filter(black).length;return b===0?'red':b>=alive.length-b?'black':null;}
function validate(g){const count=r=>g.seats.filter(p=>p.role===r).length;return g.seats.length===10&&count('civil')===6&&count('sheriff')===1&&count('mafia')===2&&count('don')===1;}
function result(g){const b=g.ballot,values=b.candidates.map(i=>Number(b.votes[i]||0));const max=Math.max(...values);return b.candidates.filter((i,k)=>values[k]===max);}
const api={roles,black,create,nextAlive,startDay,foul,remove,winner,validate,result};if(typeof module!=='undefined')module.exports=api;root.MNY=api;
})(typeof window!=='undefined'?window:globalThis);
