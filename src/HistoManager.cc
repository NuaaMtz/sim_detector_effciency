#include "HistoManager.hh"
#include <G4Types.hh>
#include <g4root_defs.hh>


HistoManager::HistoManager(G4String filename,DEConstruction* construction ):ffilename(filename),fFactoryOn(false),fconstruction(construction){

}

HistoManager::~HistoManager(){

}

void HistoManager::Book(){
    // 实例化
    G4Root::G4AnalysisManager* analysisManager = G4Root::G4AnalysisManager::Instance();
    analysisManager->SetVerboseLevel(1);
    analysisManager->SetNtupleMerging(true);// 自动合并

    // 创建文件
    // 文件名要和探测器挂钩
    G4double radius=fconstruction->GetNaIRadius();
    G4double poz_z=fconstruction->GetNaIPositionZ();
    // analysisManager->OpenFile(ffilename+".root");
    analysisManager->OpenFile(ffilename + 
                          "_R" + std::to_string(radius).replace(
                              std::to_string(radius).find('.'), 1, "p") +
                          "_Z" + std::to_string(poz_z).replace(
                              std::to_string(poz_z).find('.'), 1, "p") + 
                          ".root");

    // 创建结构
    analysisManager->CreateNtuple("tree_save_evnets_energy", "deposite energy at event level");
    analysisManager->CreateNtupleDColumn("energy");
    analysisManager->FinishNtuple(0);

    analysisManager->CreateNtuple("tree_save_property", "property setting");
    analysisManager->CreateNtupleDColumn("source-detector distance");
    analysisManager->FinishNtuple(1);

    analysisManager->CreateNtuple("tree_save_steps_energy", "deposite energy at step level");
    analysisManager->CreateNtupleDColumn("energt");
    analysisManager->FinishNtuple(2);

    // 标记为文件已创建
    fFactoryOn=true;


    
}

void HistoManager::Save(){
    // 只有文件创建了才保存
    if(!fFactoryOn)
        return;
    auto analysisManager = G4Root::G4AnalysisManager::Instance();
    analysisManager->Write();
    analysisManager->CloseFile();
    delete G4Root::G4AnalysisManager::Instance();
    fFactoryOn=false;
}

void HistoManager::FillEventsDeposite(G4double energy) {

    auto analysisManager = G4Root::G4AnalysisManager::Instance();
    analysisManager->FillNtupleDColumn(0, 0, energy);
    analysisManager->AddNtupleRow(0);
}

void HistoManager::FillProperty(G4double sourceDetectorDistance) {

    auto analysisManager = G4Root::G4AnalysisManager::Instance();
    analysisManager->FillNtupleDColumn(1, 0, sourceDetectorDistance);
    analysisManager->AddNtupleRow(1);
}

void HistoManager::FillStepsDeposite(G4double energy){
    auto analysisManager = G4Root::G4AnalysisManager::Instance();
    analysisManager->FillNtupleDColumn(2, 0, energy);
    analysisManager->AddNtupleRow(2);
}