import {mkdir, copyFile} from 'node:fs/promises';
await mkdir('frontend/vendor', {recursive: true});
await copyFile('node_modules/echarts/dist/echarts.min.js', 'frontend/vendor/echarts.min.js');
await copyFile('node_modules/echarts/LICENSE', 'frontend/vendor/ECHARTS-LICENSE.txt');
console.log('ECharts bundled locally.');
