#include "DEConstruction.hh"
#include <G4VPhysicalVolume.hh>
#include <G4VUserDetectorConstruction.hh>

DEConstruction::DEConstruction()
    : G4VUserDetectorConstruction(), f_logical_sd_NaI(nullptr),
      f_physical_sd_NaI(nullptr), f_logical_target_W(nullptr),
      f_physical_target_W(nullptr), radius(30 * cm), pos_z(0.5 * m),
      targetRadius(1.0 * cm), fEnableTargetW(true) {}

DEConstruction::~DEConstruction() {}

G4VPhysicalVolume *DEConstruction::Construct() {
  //* 世界相关
  // 世界材料定义
  G4NistManager *nist = G4NistManager::Instance();
  G4Material *world_mat = nist->FindOrBuildMaterial("G4_AIR");
  world_mat = nist->FindOrBuildMaterial("G4_Galactic"); // 真空
  if (!world_mat) {
    std::cout << "世界材料定义出现问题!" << std::endl;
  }
  // 世界尺寸定义(都是全值)
  G4double world_size_x = 2 * m;
  G4double world_size_y = 2 * m;
  G4double world_size_z = 2 * m;
  // 世界实现
  G4Box *solidWorld =
      new G4Box("World", world_size_x / 2, world_size_y / 2, world_size_z / 2);
  G4LogicalVolume *logicWorld =
      new G4LogicalVolume(solidWorld, world_mat, "World");
  G4VPhysicalVolume *physWorld =
      new G4PVPlacement(0, G4ThreeVector(), logicWorld, "World", 0, false, 0);

  if (fEnableTargetW) {
    // XrayTube 模式下才放置钨靶
    G4Material *targetW = nist->FindOrBuildMaterial("G4_W");
    G4Sphere *solidTargetW = new G4Sphere("Target_W", 0., targetRadius, 0. * deg,
                                          360. * deg, 0. * deg, 180. * deg);
    f_logical_target_W = new G4LogicalVolume(solidTargetW, targetW, "Target_W");
    f_physical_target_W = new G4PVPlacement(
        nullptr, G4ThreeVector(0, 0, 0), f_logical_target_W, "Target_W",
        logicWorld, false, 0);
  } else {
    f_logical_target_W = nullptr;
    f_physical_target_W = nullptr;
  }

  Define_NaI_Detector();

  return physWorld;
}

// 定义一个参数化的碘化钠(NaI)球体探测器，并将其放置在z轴正半轴处
// 参数说明：可调节半径(radius)和探测器中心的z轴位置(pos_z)
// 使用方式示例：在Construct()中调用此函数实现NaI探测器的添加

void DEConstruction::Define_NaI_Detector() {
  // 这两个参数可被宏命令控制
  // radius = 5.0 * cm; // 球体半径，可按需调整
  // pos_z = 0.5 * m;     // 球体中心在z轴的位置，可按需调整

  std::cout<<"半径="<<radius<<std::endl;
  // 获得NiI材料
  G4NistManager *nist = G4NistManager::Instance();
  G4Material *NaI_mat = nist->FindOrBuildMaterial("G4_SODIUM_IODIDE");
  if (!NaI_mat) {
    std::cout << "没有找到G4_SODIUM_IODIDE材料!" << std::endl;
    return;
  }

  // 获取逻辑世界体
  G4LogicalVolume *logicWorld =
      G4LogicalVolumeStore::GetInstance()->GetVolume("World");
  if (!logicWorld) {
    std::cout << "未找到名为'World'的逻辑体!" << std::endl;
    return;
  }

  // 构建球体
  G4Sphere *solidNaI = new G4Sphere("NaI_Detector",
                                    0.,         // 内半径
                                    radius,     // 外半径
                                    0. * deg,   // phi起始
                                    360. * deg, // phi终止
                                    0. * deg,   // theta起始
                                    180. * deg  // theta终止
  );

  // 创建逻辑体
  f_logical_sd_NaI=
      new G4LogicalVolume(solidNaI, NaI_mat, "NaI_Detector");

  // 物理体：将球体放置在z轴正方向pos_z处
  f_physical_sd_NaI=new G4PVPlacement(nullptr,                    // 无旋转
                    G4ThreeVector(0, 0, pos_z), // 定位到z轴正半轴
                    f_logical_sd_NaI,                   // 逻辑体
                    "NaI_Detector",             // 名称
                    logicWorld,                 // 母体
                    false,                      // 不检查重叠
                    0                           // 副本编号
  );

  // --- 说明 ---
  // 上述定义实现了一个半径为radius的NaI球体，球心位于(0,0,pos_z)。
  // 可以通过调整radius和pos_z，实现参数化探测器尺寸与位置。
}