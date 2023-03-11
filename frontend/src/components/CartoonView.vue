<template>
    <h1> SMPL2Cartoon Demo</h1>
    <div class="buttonContainer">
        <el-select  v-model="sequenceName" placeholder="SMPL Motion" class="selector" @change="motionSelectChange">
            <el-option v-for="(item,index) in sequenceNames" :key="index" :value="item">
        </el-option>
        </el-select><br><br>
        <el-button class="btn" @click="setFBXModelPath(1)">Example Model1</el-button>
        <el-button class="btn" @click="setFBXModelPath(2)">Example Model2</el-button> <br><br>
        <el-button class="btn" @click="transferFunc(0)">Random Some Pose</el-button>
        <el-button class="btn" @click="transferFunc(1)">Sequence-wise Transfer</el-button>
        </div>

        <div :width="containerWidth">
        <el-upload
        class="uploadFBX"
        drag
        action="some misc"
        :http-request="uploadFBXModel"
         >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
        Drop your fbx model here or <em>click to upload</em>
        </div>
        <template #tip>
        <div class="el-upload__tip">
            some fbx model
        </div>
        </template>
        </el-upload>
        </div>

    <div class="transfer-progress">
    <!-- <el-progress type="dashboard" :percentage="percentage" :color="colors" /> -->
    <el-progress type="dashboard" :percentage="percentage" :color="colors" />
    <p> Sequence Transfer Progress </p>
  </div>


    <div id="wrapper">
    <div id="smplContainer" class="viewContainer" >
        <video :height="containerHeight" :width="containerWidth" id="motionPlayer" autoplay="true" loop="true"></video>
    </div>
    <div id="modelContainer" class="viewContainer" >
        <canvas id="modelCanvas" :height="containerHeight" :width="containerWidth"></canvas>
    </div>
    <div id="cartoonContainer" class="viewContainer">
        <canvas id="cartoonCanvas" :height="containerHeight" :width="containerWidth"></canvas>
    </div>

    </div>
    
    
    <div class="downloadSequence">
        <el-button class="btn" @click="downloadResources(0)">Download Parsed Model</el-button>
        <el-button class="btn" @click="downloadResources(1)">Download Animated Sequence</el-button>
    </div>
</template>


<script>
    import { UploadFilled } from '@element-plus/icons-vue'
    import { onMounted, ref } from 'vue'
    import { Minus, Plus } from '@element-plus/icons-vue'

    import * as THREE from 'three';

    import Stats from 'three/examples/jsm/libs/stats.module.js';

    import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
    import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js';
    import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'; 
    import { MTLLoader } from 'three/examples/jsm/loaders/MTLLoader.js';
    // for the cartoon container (transfer)
    let scene, renderer, cartoonModel, camera;
    
    let activateAnimateObject; 
    let animateObjects = new Array();
    // for the modelContainer 
    let modelScene, modelRenderer, modelCamera, fbxModel, fbxModelPath; 

    export default {
        name: 'CartoonView', 
        data() {
            return {
                containerWidth: window.innerWidth / 4,
                containerHeight: window.innerWidth / 5, 
                // for progress bar related
                colors: [
                    { color: '#f56c6c', percentage: 20 },
                    { color: '#e6a23c', percentage: 40 },
                    { color: '#5cb87a', percentage: 60 },
                    { color: '#1989fa', percentage: 80 },
                    { color: '#6f7ad3', percentage: 100 },
                ],
                objLoadedAll: false, 
                percentage: 0, 
                timestamp: 0, 
                animateFPS: 14, 
                // activateAnimateObject: null, 
                // animateObjects: [],
                objPaths: [],
                animateObjectIndex: 0, 
                animateReadyIndices: [], 
                motionPlayer: null, 
                sequenceName: null, 
                sequenceNames: [],
                serverUrl: 'http://127.0.0.1:5000',
                // serverUrl: 'http://121.5.67.94:5905',
                loadFBXModel: false, 
                cartoonMaterial: '', 
                FrameId: 0, 
                stats: null, 
                objDirectory: '/models/obj/ch14/',
                mtlName: 'Ch14_nonPBR_intermediate.mtl', 
                clock: new THREE.Clock(),
                mixer: null, 
                    clearCache : (item) => {
                    item.geometry.dispose(); 
                    item.material.dispose();
                },
                removeObj: (obj) => {
                    let arr = obj.children.filter((x) => x);
                    arr.forEach((item) => {
                        if(item.children.length) {
                            this.removeObj(item);
                        } else{
                            this.clearCache(item);
                            item.clear();
                        }
                    })
                    obj.clear();
                    arr = null; 
                }
            }
        }, 
        methods: {
            initModelView() {
                // console.log('window height and width', window.innerHeight, window.innerWidth);
                // console.log(window.screen.height, window.screen.width);
                const smplContainer = document.getElementById( 'smplContainer' );
                // console.log(smplContainer.clientHeight, smplContainer.clientWidth);
                // console.log('--smplcontainer--');

                const that = this; 
                const container = document.getElementById( 'modelContainer' );
                console.log('model container', container.clientHeight, container.clientWidth);
                const modelCanvas = document.getElementById( 'modelCanvas' );
                console.log("modelCanvas height and widith", modelCanvas.height, modelCanvas.width);

                this.modelCamera = new THREE.PerspectiveCamera( 45, modelCanvas.width / modelCanvas.height, 1, 2000 );
                this.modelCamera.position.set( 0, 80, 220 );

                this.modelScene = new THREE.Scene();
                this.modelScene.background = new THREE.Color( 0xa0a0a0 );
                this.modelScene.fog = new THREE.Fog( 0xa0a0a0, 200, 1000 );

                const hemiLight = new THREE.HemisphereLight( 0xffffff, 0x444444 );
                hemiLight.position.set( 0, 200, 0 );
                this.modelScene.add( hemiLight );

                const dirLight = new THREE.DirectionalLight( 0xffffff );
                dirLight.position.set( 0, 200, 100 );
                dirLight.castShadow = true;
                dirLight.shadow.camera.top = 180;
                dirLight.shadow.camera.bottom = - 100;
                dirLight.shadow.camera.left = - 120;
                dirLight.shadow.camera.right = 120;
                this.modelScene.add( dirLight );

                // ground
                const mesh = new THREE.Mesh( new THREE.PlaneGeometry( 2000, 2000 ), new THREE.MeshPhongMaterial( { color: 0x999999, depthWrite: false } ) );
                mesh.rotation.x = - Math.PI / 2;
                mesh.receiveShadow = true;
                this.modelScene.add( mesh );

                const grid = new THREE.GridHelper( 2000, 20, 0x000000, 0x000000 );
                grid.material.opacity = 0.2;
                grid.material.transparent = true;
                this.modelScene.add( grid );
                
                this.modelRenderer = new THREE.WebGLRenderer( { alpha: true, antialias: true , canvas: modelCanvas } );

                // console.log('dpr', window.devicePixelRatio);
                // this.modelRenderer.setPixelRatio( window.devicePixelRatio );
                this.modelRenderer.setPixelRatio(1);
                this.modelRenderer.setSize( modelCanvas.width, modelCanvas.height );
                this.modelRenderer.shadowMap.enabled = true;

                this.modelRenderer.render(this.modelScene, this.modelCamera);

                // window.addEventListener( 'resize', this.onWindowResize );

            },
            initTransferView() {
                const that = this; 
                const container = document.getElementById( 'cartoonContainer' );
                const cartoonCanvas = document.getElementById( 'cartoonCanvas' );
                // console.log("cartoonCanvas height and width", cartoonCanvas.height, cartoonCanvas.width);

                this.animateObjects = new Array();
                this.camera = new THREE.PerspectiveCamera( 45, cartoonCanvas.width / cartoonCanvas.height, 1, 2000 );
                this.camera.position.set( 0, 140, 240 );

                this.scene = new THREE.Scene();
                this.scene.background = new THREE.Color( 0xa0a0a0 );
                this.scene.fog = new THREE.Fog( 0xa0a0a0, 200, 1000 );
                // return 
                const hemiLight = new THREE.HemisphereLight( 0xffffff, 0x444444 );
                hemiLight.position.set( 0, 200, 0 );
                this.scene.add( hemiLight );

                const dirLight = new THREE.DirectionalLight( 0xffffff );
                dirLight.position.set( 0, 200, 100 );
                dirLight.castShadow = true;
                dirLight.shadow.camera.top = 180;
                dirLight.shadow.camera.bottom = - 100;
                dirLight.shadow.camera.left = - 120;
                dirLight.shadow.camera.right = 120;
                this.scene.add( dirLight );

                // scene.add( new THREE.CameraHelper( dirLight.shadow.camera ) );

                // ground
                const mesh = new THREE.Mesh( new THREE.PlaneGeometry( 2000, 2000 ), new THREE.MeshPhongMaterial( { color: 0x999999, depthWrite: false } ) );
                mesh.rotation.x = - Math.PI / 2;
                mesh.receiveShadow = true;
                this.scene.add( mesh );

                const grid = new THREE.GridHelper( 2000, 20, 0x000000, 0x000000 );
                grid.material.opacity = 0.2;
                grid.material.transparent = true;
                this.scene.add( grid );
                
                this.renderer = new THREE.WebGLRenderer( { alpha: true, antialias: true , canvas: cartoonCanvas } );

                // this.renderer.setPixelRatio( window.devicePixelRatio );
                this.renderer.setPixelRatio( 1 );
                this.renderer.setSize( cartoonCanvas.width, cartoonCanvas.height );
                this.renderer.shadowMap.enabled = true;
                this.renderer.render(this.scene, this.camera);
                // container.appendChild( this.renderer.domElement );

                const controls = new OrbitControls( this.camera, this.renderer.domElement );
                controls.target.set( 0, 100, 0 );
                controls.update();

                // window.addEventListener( 'resize', this.onWindowResize );

                // stats
                // this.stats = new Stats();
                // container.appendChild( this.stats.dom );

            
            }, 

            async transferFunc(mode){
                if(typeof(this.sequenceName) == 'undefined' || this.sequenceName == null){
                    alert('pls choose one motion sequence!');
                    return ; 
                }
                let formData = new FormData(); 
                console.log(mode, this.sequenceName, this.fbxModelPath);
                formData.append("mode", mode == 0 ? "random" : "sequence");
                formData.append("sequenceName", this.sequenceName);    // doesn't matter 
                formData.append("fbxPath", this.fbxModelPath);
                // for(let [name, value] of formData){
                //     alert(`${name}=${value}`);
                // }
                this.percentage = 1; 

                let response = await fetch(
                    this.serverUrl + '/transfer', {
                        'method': 'POST', 
                        body: formData
                    }
                ).catch(() => {
                    console.log("randompose transfer fail!");
                    alert("fbx model parse fail!");
                });
                if(response.ok){ 
                    // at least now the fbx model has been parsed 
                    this.percentage = 10;
                    let resJson = await response.json();
                    this.objPaths.length = 0; 
                    console.log(resJson['objPath']);
                    // this.objPaths.push(resJson['objPath']);
                    this.objPaths = resJson['objPath'];
                    this.objDirectory = resJson['objDirectory'];
                    this.mtlName = resJson['mtlName'];
                    console.log('begin to download models');
                    this.downloadTransferModel();
                    console.log('download model finished');
                }
            },

            downloadTransferModel(){
                const that = this; 
                // clear the values 
                this.animateObjects.length = 0; 
                this.animateReadyIndices.length = 0;
                this.animateObjectIndex = 0; 
                new MTLLoader()
                .setPath( this.objDirectory )
                .load( this.mtlName, function ( materials ) {
                    materials.preload();
                    console.log(materials);
                    that.cartoonMaterial = materials; 
                    that.objLoadedAll = false; 
                    console.log("directory", that.objDirectory);
                    console.log("mtl", that.mtlName);
                    
                    let objLoader = new OBJLoader().setMaterials(that.cartoonMaterial).setPath(that.objDirectory);
                    for(let urlPair of Object.entries(that.objPaths)){
                        objLoader.load(urlPair[1], function(object){
                            object.traverse( function ( child ) {
                                if ( child.isMesh ) {
                                    child.castShadow = true;
                                    child.receiveShadow = true;
                                }
                            } );
                            // console.log(object);
                            that.animateObjects.push(object);
                            that.animateReadyIndices.push(parseInt(urlPair[0]));
             
                            that.percentage = parseInt(that.animateObjects.length * 100. / that.objPaths.length);
                            // console.log(that.percentage);
                            if(that.percentage < 10){
                                that.percentage = 10; 
                            }
                            if(that.percentage > 95){
                                that.objLoadedAll = true; 
                                // here we reset the video player 
                                that.motionPlayer.currentTime = 0; 
                                that.motionPlayer.play();
                            }
                        })
                    }
                });
            },
            
            animate() {
                const container = document.getElementById( 'modelContainer' );
                console.log('model container', container.clientHeight, container.clientWidth);

                const that = this; 
                requestAnimationFrame( this.animate );

                const delta = this.clock.getDelta();
                this.timestamp += delta; 
                let singleFrameTime = 1 / this.animateFPS;
                if(this.timestamp > singleFrameTime && this.objLoadedAll){
                    // console.log('should rendering new object');
                    let realIndex = this.animateReadyIndices.indexOf(this.animateObjectIndex % this.animateObjects.length);
                    this.activateAnimateObject = this.animateObjects[realIndex];
                    this.scene.add(this.activateAnimateObject);
                
                    this.animateObjectIndex = (this.animateObjectIndex + 1) % this.animateObjects.length; 
                    this.camera.lookAt(this.scene.position);
                    this.renderer.render(this.scene, this.camera);
                    this.scene.remove(this.activateAnimateObject);

                    this.timestamp = (this.timestamp % singleFrameTime);
                }
                this.modelRenderer.render(this.modelScene, this.modelCamera);

                }, 
            uiInit() {
                this.motionPlayer = document.getElementById('motionPlayer');
                // fetch the video list and update 
                this.fetchMotionList();
                
            }, 
            async fetchMotionList(){
                let response = await fetch(
                    this.serverUrl + '/getSequenceNames', {
                        "method": "GET"
                    }
                ).catch(() => {
                    console.log('fetch motion list fail')
                });
                if(response.ok){
                    let tmp = await response.text();
                    this.sequenceNames = tmp.substring(2, tmp.length - 3).split(',');
                }
            },
            
            motionSelectChange(value) {
                this.sequenceName = this.sequenceName.replace('"', '');
                console.log(this.sequenceName);
                this.motionPlayer.src = this.serverUrl + '/static/motion_frontcam/videos/' + this.sequenceName + '.mp4';
                console.log('set src to', this.serverUrl + '/static/motion_frontcam/videos/' + this.sequenceName + '.mp4');
            }, 

            async uploadFBXModel(param){
                // console.log('should be done')
                const formData = new FormData()
                formData.append('fbx_model', param.file)
                let response = await fetch(
                    this.serverUrl + '/uploadFBXModel', {
                        "method": "POST", 
                        body: formData
                    }
                ).catch(() => {
                    console.log("upload fail!");
                });
                this.fbxModelPath = await response.text();
                this.fbxModelPath = this.fbxModelPath.substring(1, this.fbxModelPath.length - 2);
                console.log("set fbx model path to", this.fbxModelPath);
                this.modelChange();
            },
            // set the fbxPath (from user upload or examples)
            setFBXModelPath(modelIndex) {
                this.fbxModelPath = this.serverUrl + '/static/service/' + modelIndex + '/sample.fbx';
                this.modelChange();
            },
            // callback when user changes the fbx model 
            modelChange() {
                // model
                const that = this; 
                console.log('before we load he fbx model', this.fbxModelPath);
                const loader = new FBXLoader();
                // don't load the fbx model
                console.log(this.fbxModelPath);
                loader.load( this.fbxModelPath, function ( object ) {
                    object.traverse( function ( child ) {
                        if ( child.isMesh ) {
                            child.castShadow = true;
                            child.receiveShadow = true;
                        }
                    } );
                    if(typeof(that.fbxModel) != 'undefined'){
                        that.modelScene.remove(that.fbxModel);
                    }
                    that.fbxModel = object; 
                    that.modelScene.add( that.fbxModel );
                    that.modelRenderer.render(that.modelScene, that.modelCamera);
                } );
                
            },
            async downloadResources(mode){
                // mode 0: download parsed model only 
                // mode 1: download animated sequences 
                let formData = new FormData();
                formData.append("fbxPath", this.fbxModelPath);
                formData.append("mode", mode);
                formData.append("sequenceName", this.sequenceName);
                let response = await fetch(
                    this.serverUrl + '/downloadResources', {
                        "method": "POST", 
                        body: formData
                    }
                ).catch(() => {
                    console.log('download resources fail')
                });
                if(response.ok){
                    let zipPath = await response.text();
                    zipPath = zipPath.substring(1, zipPath.length - 2);
                    console.log('should redirect to', zipPath);
                    // window.location.replace(zipPath);
                    window.open(zipPath, "download");
                }
            }
            
        }, 
        mounted() {
            this.initModelView()
            this.initTransferView()
            this.uiInit()
            this.animate()
        }
    }

</script>

<style>
    body{
        text-align: center; 
    }
   .downloadSequence{
        display: block; 
        position: relative; 
        /* float: left;  */
        margin-top: 24%; 
        text-align:center; 
   }
   .selector{
    margin-right: 10px; 
   }
   .btn{
    display: inline 
   }
   .uploadFBX{
        height: 100px; 
        width: v-bind(containerWidth); 
        display: block; 
        /* margin-left: 40%;  */
        margin-left: 30%; 
        margin-right: 30%; 
        margin-top: 20px; 
        margin-bottom: 50px;
   }
   #wrapper{
    position:relative;
    margin-left: 3%; 
    margin-right: 3%;
    margin-top: 2%;
    /* height: 480; */
    /* width: 1920; */
    /* top:50%; */
    /* transform:translateY(50%) */
   }
    .viewContainer{
        background-color: 'red';
        position: relative; 
        border: 4px solid rgb(90, 202, 239);
        border-radius: 10px; 
        margin-left: 3%;
        width: v-bind('containerWidth');
        height: v-bind('containerHeight');
        float: left; 
        overflow: hidden; 
    }
    
    .transfer-progress{
        position: relative; 
        margin-top: 150px; 
        display: block; 
    }

    .transfer-progress .el-progress--line {
    /* margin-top: 300px; */
    margin-bottom: 0px;
    width: 350px;
    }
    .transfer-progress .el-progress--circle {
    /* margin-top: 300px;  */
    margin-right: 0px;
    }
</style>