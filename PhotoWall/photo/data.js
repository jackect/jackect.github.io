var data = [];

var dataStr = "\
sm&说明&I'm Hell Jibe,I hava a dream.作为一个程序员，我想用我们的方式纪念最后一批90后成年，背景音乐是《我们的明天》。在此十分感谢这几位朋友，部分图片来自互联网。$\
ds&董珊&大学副班长：时间会把最好的人留到最后。$\
yzj&颜兆洁&前前前前前任同桌：虽然一直生活在阴暗和沉默之中，可是不会错过每一缕晨光。$\
hyq&何亚琴&侄女：以忆为名，莫失莫忘。$\
dlf&邓龙芬&外向的小学同学：南风知我意，吹梦到西洲。$\
csq&曹思琪&乒乓球班同学：有些梦想到了老了就实现不了了，所以趁现在年轻，Go~Go~Go。$\
gg&耿耿&耿耿，八月长安作品《最好的我们》中女主角，经典台词：一厢情愿，就得愿赌服输。回忆是时光里带着温暖的余烬。$\
cyx&楚雨荨&楚雨荨，《一起去看流星雨》的女主角，经典台词：我见过自恋的，没见过你这么自恋的，我告诉你，我上辈子下辈子，上下八百辈子都不会喜欢你这个自恋狂。$\
le&李珥&李珥,苏有朋导演的《左耳》的女主角,经典台词：医学专家说左耳是靠近心脏最近的地方，甜言蜜语要说给左耳听。$\
tg&唐广&高中认识的第一个朋友：生活不止眼前的苟且还有远方的。$\
lq&龙倩&永远的小可爱：我遇见你都是人间最好的事。$\
cj&陈佳&永远的小帅哥：我爱上你都是世间最美的事。\
"

var d = dataStr.split("$");
for(var i = 0; i<d.length; i++){
  var c = d[i].split("&");
  data.push({
    img: c[0]+ ".jpg",
    caption: c[1],
    desc: c[2]
  });
}

