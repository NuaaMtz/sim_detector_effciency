# 模拟
## 使用4英寸碘化钠探测器和各种常见放射源（事件数1个亿），实现：
### 1. 测量探测器的探测效率
### 2. 能量刻度、不同源距离下的能谱


## X 光能谱分解
1. 粒子源默认为打靶源  
生成1-7.5 MeV 随机能量的电子打一个钨靶来产生光子
实现方案： 在 (0,0，-5cm)处生成电子，在（0,0,0） 处放一个半径为 1cm 的钨，打靶

2. 只保留打靶后产生的X光  
打靶后产生的光子才是我们需要的，因此打出的光子需要被标记，然后在探测中判断标记存在才可以记录沉积能。
新建了一个 track 类，然后在 step 中做标记，通过判断标记来识别次级粒子。



## X 光能谱分解V2
前面描述思路错了。 我之前想着的是，先随机质子的能量，再质子单能，再用单能拟合随机能量。
但是这样得到的可能是质子的能谱，不是我想要的光子的能谱。

新的思路是： 

- 第一步还是生成1-7.5 MeV 随机能量的电子打一个钨靶来产生光子，然后收集得到随机能量范围下质子打靶产生的次级光子的能量沉积。
具体实现还是保持 现在的 track 类，然后标记质子打靶产生的次级光子，再探测器step 中收集。 
- 用上面得到的随机能量范围下质子打靶产生的次级光子的能量沉积作为一个新的粒子源，然后抽样发射粒子，但是可以限制只抽单能光子，即某个能量附近下的光子能量。具体来说，就是读取一个 root 文件，然后获取它的某个 tree 的某个 branch 下的数据作为能谱，抽样发射。


当前实现：
1. 保留随机能量电子打靶功能，删除单能电子发射功能

保留：
``
/mydet/setSource XrayTube
``
已移除：
``
/mydet/useMonoEnergy false
``

2. 新增 ROOT 能谱抽样源，支持指定 tree/branch 和能量区间

切换到 ROOT 能谱源：
``
/mydet/setSource RootSpectrum
``

配置 ROOT 输入：
``
/mydet/setSpectrumRootFile /absolute/path/to/spectrum.root
/mydet/setSpectrumTree tree_save_steps_energy
/mydet/setSpectrumBranch energt
``

配置抽样能区（可用于近单能区间抽样）：
``
/mydet/setSpectrumMinEnergy 500 keV
/mydet/setSpectrumMaxEnergy 700 keV
``
