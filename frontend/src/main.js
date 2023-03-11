import { createApp } from 'vue'
import App from './App.vue'

// createApp(App).mount('#app')

import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';

createApp(App).use(ElementPlus).mount('#app')
