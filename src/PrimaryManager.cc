#include "PrimaryManager.hh"
#include "PrimaryGeneration.hh"
#include <G4UIcmdWithAString.hh>


// G4UImanager是全局单例管理器，不能在这里被初始化
PrimaryManager::PrimaryManager(PrimaryGeneration *primary)
    : fPrimaryGeneration(primary) {
        // 将命令名设计为"/mydet/setSource"，便于用户通过UI命令指定源
        fNameOfSource = new G4UIcmdWithAString("/mydet/setSource",
             this);
        fNameOfSource->SetGuidance("Set the radioactive source for simulation. Options: Co60, Cs137, Na22, Am241, Mn54");
        fNameOfSource->SetParameterName("sourceName", false);
    }

PrimaryManager::~PrimaryManager() = default;

void PrimaryManager::SetNewValue(G4UIcommand *command, G4String newValue) {
    // 命令正确调用
    if(command==fNameOfSource){
        // 命令调用时机正确
        if(fPrimaryGeneration){
            // 直接使用 newValue，因为G4String newValue已经是传入的字符串
            G4String NewSourceName = newValue;
            // 修改粒子源
            fPrimaryGeneration->SetSourceName(NewSourceName);
        }
    }

}