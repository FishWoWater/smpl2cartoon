<template>
    <h1> {{ msg }} </h1>
    <div id="smplPreviewContainer">
        <canvas id="smplCanvas" height="480" width="640"></canvas>
    </div>
</template>

<script>
export default {
    name: 'SMPLView', 
    data() {
        return {
            msg: 'can you see me?'
        }
    }, 
    methods: {
        
    }
}
</script>

<style>

</style>