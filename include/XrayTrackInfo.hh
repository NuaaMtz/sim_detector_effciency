#pragma once

#include <G4VUserTrackInformation.hh>

class XrayTrackInfo : public G4VUserTrackInformation {
public:
  explicit XrayTrackInfo(bool fromTaggedXray) : fFromTaggedXray(fromTaggedXray) {}
  virtual ~XrayTrackInfo() = default;

  bool IsFromTaggedXray() const { return fFromTaggedXray; }

private:
  bool fFromTaggedXray;
};
