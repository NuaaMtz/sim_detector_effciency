#pragma once 
#include <G4Types.hh>
#include <globals.hh>

class HistoManager{

    public:
        HistoManager(G4String);
        ~HistoManager();
        void Book();// 在这里创建文件
        void Save();// 在这里写入文件
        void FillEventsDeposite(G4double energy);
        void FillStepsDeposite(G4double);
        void FillProperty(G4double sourceDetectorDistance);
    private:
        G4String ffilename;
        G4bool fFactoryOn;
    
};