#pragma once

#include "G4VUserDetectorConstruction.hh"
#include <G4LogicalVolume.hh>
#include <G4Types.hh>
#include <G4VPhysicalVolume.hh>

#include "G4Box.hh"
#include "G4LogicalVolumeStore.hh"
#include "G4NistManager.hh"
#include "G4PVPlacement.hh"
#include "G4SystemOfUnits.hh"
#include "G4Sphere.hh"
class DEConstruction : public G4VUserDetectorConstruction {

public:
  DEConstruction();
  virtual ~DEConstruction();

  // 主函数
  virtual G4VPhysicalVolume *Construct() override;

// 接口
public:

G4LogicalVolume* GetLogicalSDNaI()const {return f_logical_sd_NaI;}
G4VPhysicalVolume* GetPhysicalSDNaI()const {return f_physical_sd_NaI;}

// 设置NaI球半径
void SetNaIRadius(G4double r) { radius = r; }
// 设置NaI球z轴位置
void SetNaIPositionZ(G4double z) { pos_z = z; }

G4double GetNaIRadius()const { return radius;}
G4double GetNaIPositionZ() const {return pos_z;}
void SetEnableTargetW(G4bool enable) { fEnableTargetW = enable; }
G4bool GetEnableTargetW() const { return fEnableTargetW; }
G4double GetTargetRadius() const { return targetRadius; }





  // 
  void Define_NaI_Detector();

private:
  G4LogicalVolume* f_logical_sd_NaI;
  G4VPhysicalVolume* f_physical_sd_NaI;
  G4LogicalVolume* f_logical_target_W;
  G4VPhysicalVolume* f_physical_target_W;
  G4double radius ;
  G4double pos_z;
  G4double targetRadius;
  G4bool fEnableTargetW;

public:
  G4LogicalVolume* GetLogicalTargetW() const { return f_logical_target_W; }
  G4VPhysicalVolume* GetPhysicalTargetW() const { return f_physical_target_W; }
};