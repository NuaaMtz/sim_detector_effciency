#include "ConstructionManager.hh"
#include "DEConstruction.hh"
#include <G4RunManager.hh>
#include <G4String.hh>
#include <G4UIcmdWithADoubleAndUnit.hh>
#include <G4UIcommand.hh>

ConstructionManager::ConstructionManager(DEConstruction* detector):fdetector(detector){

    // 创建宏命令用于设置源-探测器距离
    fSourceDetectorDistanceCmd = new G4UIcmdWithADoubleAndUnit("/mydet/sourceDetectorDistance", this);
    fSourceDetectorDistanceCmd->SetGuidance("Set source-detector distance. (unit: mm, cm, m, etc. Please specify, e.g., '30 mm')");
    fSourceDetectorDistanceCmd->SetParameterName("distance", false);
    fSourceDetectorDistanceCmd->SetUnitCategory("Length");
    fSourceDetectorDistanceCmd->SetRange("distance>=0.");
    fSourceDetectorDistanceCmd->AvailableForStates(G4State_PreInit, G4State_Idle);

    // 探测器半径命令
     fDetectorRadiusCmd = new G4UIcmdWithADoubleAndUnit("/mydet/detectorRadius", this);
     fDetectorRadiusCmd->SetGuidance("Set the NaI detector radius.");
     fDetectorRadiusCmd->SetParameterName("radius", false);
     fDetectorRadiusCmd->SetUnitCategory("Length");
     fDetectorRadiusCmd->SetRange("radius>0.");
     fDetectorRadiusCmd->AvailableForStates(G4State_PreInit, G4State_Idle);
}

ConstructionManager::~ConstructionManager()=default;


void ConstructionManager::SetNewValue(G4UIcommand* command,G4String newvalue){
    std::cout<<"调用命令"<<std::endl;
    // 正确调用
    if (fSourceDetectorDistanceCmd == command) {
        // 调用时机正确
        if (fdetector) {

            // 带单位传入字符串，转换为带单位的数值
            G4double distance = fSourceDetectorDistanceCmd->GetNewDoubleValue(newvalue);
            fdetector->SetNaIPositionZ(distance);
            if (G4RunManager::GetRunManager()) {
                G4RunManager::GetRunManager()->GeometryHasBeenModified();
            }
        }
    }

    else if (fDetectorRadiusCmd == command) {
        if (fdetector) {
            G4double radius = fDetectorRadiusCmd->GetNewDoubleValue(newvalue);
            fdetector->SetNaIRadius(radius);
            // std::cout<<"半径大小="<<radius<<std::endl;
            if (G4RunManager::GetRunManager()) {
                G4RunManager::GetRunManager()->GeometryHasBeenModified();
            }
        }
    }

}