<template>
  <!-- <img alt="Vue logo" src="./assets//models/obj/ch14/0.png"> -->
  <!-- <HelloWorld msg="Welcome to Your Vue.js App"/> -->
  <!-- <SMPLView> </SMPLView> -->
  <CartoonView> </CartoonView>
</template>

<script>
// import HelloWorld from './components/HelloWorld.vue'
import CartoonView from './components/CartoonView.vue'
// import SMPLView from './components/SMPLView.vue'

export default {
  name: 'App',
  components: {
    CartoonView, 
    // SMPLView
  }
}
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  /* margin-top: 60px; */
  /* top: 50%; */
  /* margin-top: 50%; */
}
</style>
