#include "PrimaryManager.hh"
#include "PrimaryGeneration.hh"
#include <G4RunManager.hh>
#include <G4UIcmdWithADoubleAndUnit.hh>
#include <G4UIcmdWithAString.hh>


// G4UImanager是全局单例管理器，不能在这里被初始化
PrimaryManager::PrimaryManager(PrimaryGeneration *primary)
    : fPrimaryGeneration(primary) {
        // 将命令名设计为"/mydet/setSource"，便于用户通过UI命令指定源
        fNameOfSource = new G4UIcmdWithAString("/mydet/setSource",
             this);
        fNameOfSource->SetGuidance("Set source mode. Options: XrayTube, RootSpectrum, Co60, Cs137, Na22, Am241, Mn54");
        fNameOfSource->SetParameterName("sourceName", false);

        fSpectrumRootFileCmd = new G4UIcmdWithAString("/mydet/setSpectrumRootFile", this);
        fSpectrumRootFileCmd->SetGuidance("Set ROOT file for RootSpectrum source.");
        fSpectrumRootFileCmd->SetParameterName("filePath", false);

        fSpectrumTreeCmd = new G4UIcmdWithAString("/mydet/setSpectrumTree", this);
        fSpectrumTreeCmd->SetGuidance("Set tree name used by RootSpectrum source.");
        fSpectrumTreeCmd->SetParameterName("treeName", false);

        fSpectrumBranchCmd = new G4UIcmdWithAString("/mydet/setSpectrumBranch", this);
        fSpectrumBranchCmd->SetGuidance("Set branch name used by RootSpectrum source.");
        fSpectrumBranchCmd->SetParameterName("branchName", false);

        fSpectrumMinEnergyCmd = new G4UIcmdWithADoubleAndUnit("/mydet/setSpectrumMinEnergy", this);
        fSpectrumMinEnergyCmd->SetGuidance("Set lower energy bound for RootSpectrum sampling.");
        fSpectrumMinEnergyCmd->SetParameterName("emin", false);
        fSpectrumMinEnergyCmd->SetUnitCategory("Energy");

        fSpectrumMaxEnergyCmd = new G4UIcmdWithADoubleAndUnit("/mydet/setSpectrumMaxEnergy", this);
        fSpectrumMaxEnergyCmd->SetGuidance("Set upper energy bound for RootSpectrum sampling.");
        fSpectrumMaxEnergyCmd->SetParameterName("emax", false);
        fSpectrumMaxEnergyCmd->SetUnitCategory("Energy");
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
            if (G4RunManager::GetRunManager()) {
                G4RunManager::GetRunManager()->GeometryHasBeenModified();
            }
        }
    } else if (command == fSpectrumRootFileCmd) {
        if (fPrimaryGeneration) {
            fPrimaryGeneration->SetSpectrumRootFile(newValue);
        }
    } else if (command == fSpectrumTreeCmd) {
        if (fPrimaryGeneration) {
            fPrimaryGeneration->SetSpectrumTreeName(newValue);
        }
    } else if (command == fSpectrumBranchCmd) {
        if (fPrimaryGeneration) {
            fPrimaryGeneration->SetSpectrumBranchName(newValue);
        }
    } else if (command == fSpectrumMinEnergyCmd) {
        if (fPrimaryGeneration) {
            const G4double minEnergy = fSpectrumMinEnergyCmd->GetNewDoubleValue(newValue);
            fPrimaryGeneration->SetSpectrumMinEnergy(minEnergy);
        }
    } else if (command == fSpectrumMaxEnergyCmd) {
        if (fPrimaryGeneration) {
            const G4double maxEnergy = fSpectrumMaxEnergyCmd->GetNewDoubleValue(newValue);
            fPrimaryGeneration->SetSpectrumMaxEnergy(maxEnergy);
        }
    }

}